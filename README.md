## Introduction

Default User is admin with password admin, for details please check auth_tools page.

This project started as a personal tool that I created for my own use and to share with friends. As more functions were added and I noticed that no similar project existed on GitHub, I decided to publish it.

Key features include:
- **Telegram Bot Interface:** Engage with the AI assistant directly via Telegram.
- **Local Streamlit UI:** Test your agent before deploying the bot, or simply use as a tool in local.
- **Functionality Extension:** Utilize utility functions for web crawling, real-time weather updates, youtube video transcription, etc. You can keep creating your tools and AI workflows.

## Running the Telegram Bot
1. Install Docker if you haven’t already:  https://docs.docker.com/get-docker/
2. Clone this repository to your local machine:
3. Open .env and fill in your credentials:

    - APP_ID and API_HASH Can be found in: https://my.telegram.org/auth    
    - BOT_TOKEN: Search @BotFather in Telegram and follow the instructions
    - OPENAI_API_KEY: Obtain from OpenAI: https://platform.openai.com/
    - ACCESS_PASSWORD: The password will be used to verify access.

4. Then, navigate to the project folder and build the image:
    - `cd /path/to/your/project`
    - `docker build --tag gptbot:latest .`
5. To run the Docker container, use the following command:
    - `docker-compose up`
6. Once the container is running, go to Telegram and send the /start command to your bot. 
7. Input your password you configured before.

etc. 
if you want to handle messages that mention the bot, please check the comment in bot.py for how to added a pattern.
Then you may add it to a group chat, However, you still need to send the password directly to the bot in a private chat.

## Running in the local with streamlit UI
1. Make sure you have Python3 installed.
2. Install the yt-dlp ffmpeg module:
`brew install yt-dlp ffmpeg` 
3. Install the virutal environment:
`python3 -m venv .venv`
4. Change the .env file with your APIKEY: 
    -> OPENAI_API_KEY Obtain from OpenAI: https://platform.openai.com/
5. Install dependencies:
`pip3 install -r requirements.txt`
6. Start the local server:
`streamlit run streamlit_app.py`

## Showcase

![Diagram](readme/streamlit_showcase.JPEG)
![Diagram](readme/telegrambot_showcase.JPEG)

