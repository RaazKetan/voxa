import os, json, asyncio, base64
from dotenv import load_dotenv
from quart import Quart, request, Response, websocket
import numpy as np
import websockets

load_dotenv()

# ---- Config ----
PUBLIC_BASE = os.environ["PUBLIC_BASE_URL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-live")
SAMPLE_RATE = int(os.getenv("GEMINI_SAMPLE_RATE", "8000"))

# Gemini Live (Realtime) WebSocket endpoint (v1beta)
# Official WS endpoint per docs:
# wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent
GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

# ---- μ-law <-> PCM16 helpers (8kHz mono) ----
MU_LAW_BIAS = 0x84
CLIP = 32635

def mulaw_decode(mu_bytes: bytes) -> bytes:
    """μ-law -> PCM16 bytes"""
    if not mu_bytes:
        return b""
    mu = np.frombuffer(mu_bytes, dtype=np.uint8)
    mu = ~mu
    sign = mu & 0x80
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    magnitude = ((mantissa << 4) + 0x08) << (exponent + 3)
    magnitude = magnitude - MU_LAW_BIAS
    pcm = np.where(sign != 0, -magnitude, magnitude).astype(np.int16)
    return pcm.tobytes()

def mulaw_encode(pcm16: bytes) -> bytes:
    """PCM16 -> μ-law bytes (fast approx, good enough for telephony)"""
    if not pcm16:
        return b""
    x = np.frombuffer(pcm16, dtype=np.int16).astype(np.int32)
    sign = (x < 0).astype(np.int32)
    x = np.clip(np.abs(x), 0, CLIP)
    # Approximate μ-law companding
    exponent = np.floor(np.log2((x / 16.0) + 1e-9)).astype(np.int32)
    exponent = np.clip(exponent, 0, 7)
    mantissa = (x >> (exponent + 3)) & 0x0F
    ulaw = (~((sign << 7) | (exponent << 4) | mantissa)).astype(np.uint8)
    return ulaw.tobytes()

# ---- Quart app ----
app = Quart(__name__)
app.config.setdefault("PROVIDE_AUTOMATIC_OPTIONS", True)

@app.post("/voice")
async def voice():
    """
    Twilio hits this on incoming call.
    We instruct Twilio to open a *bidirectional* Media Stream to our WS endpoint.
    """
    ws_url = f"{PUBLIC_BASE.replace('http', 'ws')}/twilio-stream"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Connecting you to the assistant.</Say>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="format" value="audio/x-mulaw;rate={SAMPLE_RATE}"/>
      <Parameter name="bidirectional" value="true"/>
    </Stream>
  </Connect>
</Response>"""
    return Response(twiml, mimetype="text/xml")

@app.websocket("/twilio-stream")
async def twilio_stream():
    """
    Bridge between Twilio's Media Stream and Gemini Live Realtime WS.
    - Receive μ-law 8k from Twilio -> decode -> send PCM16 to Gemini
    - Receive PCM16 audio from Gemini -> encode μ-law -> send to Twilio
    """
    # Open Gemini WS
    # Auth with API key via query param + Authorization header (either is accepted).
    headers = [("Authorization", f"Bearer {GEMINI_API_KEY}")]
    gem_url = GEMINI_WS_URL + f"?key={GEMINI_API_KEY}"
    async with websockets.connect(gem_url, extra_headers=headers, ping_interval=20, ping_timeout=20) as gem_ws:

        # Send initial setup/config per Gemini Live spec
        # - model
        # - response modalities include audio
        # - speech config (output audio format)
        setup = {
            "setup": {
                "model": GEMINI_MODEL,
                "generationConfig": {
                    "responseModalities": ["AUDIO", "TEXT"],
                    "speechConfig": {
                        "voiceConfig": { "voiceName": "Charon" }  # any supported voice; optional
                    },
                    "maxOutputTokens": 2048,
                    "temperature": 0.7
                },
                "realtimeInput": {
                    "automaticActivityDetection": {},   # keep default VAD
                },
                "systemInstruction": "You are a concise, polite phone agent. Keep answers to 1–2 sentences."
            }
        }
        await gem_ws.send(json.dumps(setup))

        # Task 1: forward Twilio audio -> Gemini (decode μ-law to PCM16)
        async def pump_twilio_to_gemini():
            while True:
                raw = await websocket.receive()
                msg = json.loads(raw)

                ev = msg.get("event")
                if ev == "stop":
                    # Caller hung up
                    try:
                        await gem_ws.close()
                    finally:
                        break

                if ev == "media":
                    b64 = msg["media"]["payload"]
                    ulaw = base64.b64decode(b64)
                    pcm16 = mulaw_decode(ulaw)
                    await gem_ws.send(json.dumps({
                        "realtimeInput": {
                            "audio": {
                                "data": base64.b64encode(pcm16).decode("ascii"),
                                "mimeType": f"audio/pcm;rate={SAMPLE_RATE}"
                            }
                        }
                    }))

                # (optional) forward DTMF, marks, etc.

        # Task 2: forward Gemini audio -> Twilio (encode PCM16 to μ-law, 20ms pacing)
        async def pump_gemini_to_twilio():
            while True:
                try:
                    raw = await gem_ws.recv()
                except websockets.ConnectionClosed:
                    break

                evt = json.loads(raw)

                # Text content (optional logging or tool routing)
                if "serverContent" in evt:
                    # You can inspect evt["serverContent"]["modelTurn"]["parts"] for text
                    pass

                # Audio chunks
                # Depending on the server message shape, audio may be in serverContent parts
                # or as a dedicated outputAudio field (both are documented by the Live API).
                # We handle both.
                audio_chunks = []

                # case 1: top-level outputAudio
                if "outputAudio" in evt:
                    audio_chunks.append(evt["outputAudio"]["data"])

                # case 2: audio embedded in serverContent.parts
                sc = evt.get("serverContent")
                if sc and "modelTurn" in sc and "parts" in sc["modelTurn"]:
                    for p in sc["modelTurn"]["parts"]:
                        if isinstance(p, dict) and p.get("audio"):
                            audio_chunks.append(p["audio"]["data"])

                # stream each chunk back to Twilio
                for b64_pcm in audio_chunks:
                    pcm16 = base64.b64decode(b64_pcm)
                    ulaw = mulaw_encode(pcm16)

                    # Twilio expects ~20ms frames: 160 bytes μ-law @ 8kHz
                    frame = 160
                    for i in range(0, len(ulaw), frame):
                        payload = base64.b64encode(ulaw[i:i+frame]).decode("ascii")
                        await websocket.send(json.dumps({
                            "event": "media",
                            "media": {"payload": payload}
                        }))
                        await asyncio.sleep(0.02)

                    # Send a mark so Twilio knows playback chunk finished
                    await websocket.send(json.dumps({
                        "event": "mark",
                        "mark": {"name": "gemini-chunk"}
                    }))

        # Run both pumps concurrently
        await asyncio.gather(pump_twilio_to_gemini(), pump_gemini_to_twilio())

if __name__ == "__main__":
    import hypercorn.asyncio, hypercorn.config, asyncio as aio
    cfg = hypercorn.config.Config()
    cfg.bind = ["0.0.0.0:5050"]
    aio.run(hypercorn.asyncio.serve(app, cfg))
