import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from STT import get_stt_instance

def main():
    """Test the STT module."""
    print("Initializing Speech-to-Text...")
    stt = get_stt_instance()
    print("  Calibrating microphone (2 seconds)...")
    stt.calibrate_microphone(duration=2)
    print("\n>>> Speak now! <<<\n")
    
    try:
        text = stt.listen_and_recognize(timeout=5, phrase_time_limit=8)
        if text:
            print(f"You said: {text}")
        else:
            print("No speech detected")
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
