FROM ghcr.io/astral-sh/uv:debian

# Install dependencies
RUN apt-get update && \
	apt-get install -y --no-install-recommends \
		gcc \
		git \
		python3-dev \
		libpq-dev \
		make && \
	rm -rf /var/lib/apt/lists/*

# Copy code
WORKDIR /app
COPY . .

# Run FastAPI
CMD ["uv", "run", "uvicorn", "app:app", "--port", "8000"]
