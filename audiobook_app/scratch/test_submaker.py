import edge_tts
import asyncio

async def test():
    submaker = edge_tts.SubMaker()
    print("Methods and attributes of SubMaker:")
    print(dir(submaker))
    
    # Try to feed a mock WordBoundary
    mock_msg = {
        "type": "WordBoundary",
        "offset": 1000000,
        "duration": 500000,
        "text": "Hello"
    }
    try:
        submaker.feed(mock_msg)
        print("Fed mock message.")
    except Exception as e:
        print(f"Error feeding message: {e}")
        
    if hasattr(submaker, 'cues'):
        print(f"Found 'cues' attribute. Length: {len(submaker.cues)}")
        if submaker.cues:
            cue = submaker.cues[0]
            print(f"Cue structure: {dir(cue)}")
    else:
        print("No 'cues' attribute found.")

if __name__ == "__main__":
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"Test failed: {e}")
