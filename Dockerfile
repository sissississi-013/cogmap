FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# WANDB_API_KEY, OPENAI_API_KEY and Modal credentials come from the environment at run time
ENTRYPOINT ["python", "run_demo.py"]
CMD ["--synthetic", "--out", "out/docker"]
