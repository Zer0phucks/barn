import asyncio
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

async def test():
    client = genai.Client(api_key=api_key)
    prompt = "Go to cyberbackgroundchecks.com and find the first resident listed for 2643 MARKET ST OAKLAND CA 94607. Who is it? Reply with just their name."
    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
        )
    )
    print(response.text)

asyncio.run(test())
