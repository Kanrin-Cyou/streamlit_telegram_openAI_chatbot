FROM python:3.12-slim
COPY . .
RUN apt-get update
RUN apt-get install -y curl ffmpeg
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
RUN chmod a+rx /usr/local/bin/yt-dlp
RUN yt-dlp --version
RUN pip3 install -r requirements.txt
CMD ["python", "-u", "/bot.py"]