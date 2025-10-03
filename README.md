# transcribe-backend
Backend built on FastAPI for the SUNET transcription service

## Development environment setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
	```bash
	source venv/bin/activate
	```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Edit the environment settings, should be in a file named `.env`. The following settings should be sufficient for most cases:
	```env
	API_DATABASE_URL="sqlite:///jobs.db"
	API_DEBUG=True
	API_PREFIX="/api/v1"
	API_VERSION="0.1.0"
	API_TITLE="Whisper REST backend"
	API_DESCRIPTION="A REST API for the Whisper ASR model"
	API_FILE_STORAGE_DIR=<Your file storage directory>
	API_SECRET_KEY=<Your secret key>
	API_CLIENT_VERIFICATION_ENABLED=true/false

	OIDC_CLIENT_ID = <Your OIDC client ID>
	OIDC_CLIENT_SECRET = <Your OIDC client secret>
	OIDC_METADATA_URL = <Your OIDC provider metadata URL>
	OIDC_SCOPE = openid,profile,email
	OIDC_REFRESH_URI = <Your token refresh endpoint>
	OIDC_REDIRECT_URI=http://localhost:8000/api/auth
	OIDC_FRONTEND_URI=http://localhost:8888
	```

5. Run the application:
	```bash
	python3 -m fastapi dev app.py --host=0.0.0.0
	```
