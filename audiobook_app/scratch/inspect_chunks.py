import edge_tts
import asyncio

async def test_voice(voice):
    text = "The quick brown fox jumps over the lazy dog."
    communicate = edge_tts.Communicate(text, voice)
    
    print(f"Testing voice: {voice}")
    found_types = set()
    async for chunk in communicate.stream():
        ctype = chunk.get('type')
        if ctype != 'audio':
            found_types.add(ctype)
    print(f"  Types: {found_types}")
    return found_types

async def main():
    voices = ["en-US-AriaNeural", "en-US-GuyNeural", "en-US-JennyNeural", "en-GB-RyanNeural"]
    for v in voices:
        await test_voice(v)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Test failed: {e}")
