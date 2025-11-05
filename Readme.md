# Voxa: Twilio ↔️ Gemini Live Voice Bridge

This project bridges Twilio's Media Streams (phone calls) with Google's Gemini Live (Realtime) API for real-time, bidirectional voice conversations.

## Features
- Receives phone calls via Twilio, streams audio to Gemini Live API
- Converts μ-law (Twilio) <-> PCM16 (Gemini) audio formats
- Streams Gemini's AI-generated speech back to the caller in real time
- Uses Quart (async Flask) and Hypercorn for async web + websocket handling

## Quick Start

### 1. Prerequisites
- Python 3.8+
- [ngrok](https://ngrok.com/) (for local development)
- Twilio account (with programmable voice enabled)
- Google Gemini API key (with access to Gemini Live)

### 2. Install dependencies
```sh
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root with the following:
```
PUBLIC_BASE_URL=https://<your-ngrok-domain>
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-live
GEMINI_SAMPLE_RATE=8000
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_FROM=your-twilio-number
MY_PHONE=your-mobile-number
```

### 4. Start the server
```sh
python app.py
```

Or, for production:
```sh
hypercorn app:app --bind 0.0.0.0:5050
```

### 5. Expose your server (for Twilio)
```sh
ngrok http 5050
```
Set `PUBLIC_BASE_URL` to your ngrok HTTPS URL.

### 6. Make a test call
Edit and run `make_call.py` to trigger a call from your Twilio number to your phone.

---

## File Overview
- `app.py` — Main Quart app, Twilio <-> Gemini audio bridge
- `make_call.py` — Script to trigger a test call via Twilio
- `requirements.txt` — Python dependencies

## Notes
- This is a demo/reference implementation. Use with caution for production.
- Audio is 8kHz mono μ-law (telephony standard).
- Gemini Live API and Twilio Media Streams may incur costs.

## License
MIT License

Copyright (c) 2025 Ketan Raj

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.