# YouTube Video Auto-Translation & Dubbing

A web application that loads YouTube videos and auto-translates them in real-time as they play. The application uses Deepgram for transcription, OpenAI for translation, and provides a real-time dubbed experience.

## Features

- Load and play any YouTube video
- Real-time transcription using Deepgram
- On-the-fly translation to various languages
- Synchronized display of original and translated text
- Multiple language support

## Tech Stack

### Frontend
- React with TypeScript
- TailwindCSS for styling
- React YouTube for video embedding
- WebSockets for real-time communication

### Backend
- FastAPI (Python)
- Deepgram for speech-to-text
- OpenAI for translation
- WebSockets for streaming results

## Setup Instructions

### Prerequisites

- Node.js 14+ (frontend)
- Python 3.8+ (backend)
- API keys for:
  - Deepgram (transcription)
  - OpenAI (translation)

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the template:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file to add your API keys:
   ```
   DEEPGRAM_API_KEY=your_deepgram_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

6. Start the FastAPI server:
   ```
   python src/server.py
   ```
   
   The API will be available at http://localhost:8000

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm start
   ```

   The app will be available at http://localhost:3000

## Usage

1. Open the application in your browser
2. Enter a YouTube URL in the input field
3. Select source and target languages
4. Click "Load Video" and play the video
5. As the video plays, the application will:
   - Transcribe the audio in real-time
   - Translate the transcription
   - Display both original and translated text

## Environment Variables

### Backend

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPGRAM_API_KEY` | API key for Deepgram | (Required) |
| `OPENAI_API_KEY` | API key for OpenAI | (Required) |
| `API_PREFIX` | API URL prefix | `/api/v1` |
| `DEBUG` | Debug mode | `True` |
| `BACKEND_CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |

### Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `REACT_APP_API_URL` | Backend API URL | `http://localhost:8000/api/v1` |
| `REACT_APP_WS_URL` | WebSocket URL | `ws://localhost:8000/api/v1` |

## License

MIT

## Acknowledgements

- [Deepgram](https://deepgram.com/) for speech recognition
- [OpenAI](https://openai.com/) for translation
- [FastAPI](https://fastapi.tiangolo.com/) for backend framework
- [React](https://reactjs.org/) for frontend framework 