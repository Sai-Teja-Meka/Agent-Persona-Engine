import argparse
from embodiment.soul import CharacterSoul

def main():
    parser = argparse.ArgumentParser(description="Talk to the Infinite Library")
    parser.add_argument("--char", required=True, help="Name of the character (must match Graph name)")
    args = parser.parse_args()

    print(f"👻 Summoning {args.char}...")
    try:
        soul = CharacterSoul(args.char)
        print(f"✅ {args.char} is conscious. (Type 'quit' to exit)")
        print("-" * 50)
        
        while True:
            user_input = input("You: ")
            if user_input.lower() in ["quit", "exit"]:
                break
            
            response = soul.speak(user_input)
            print(f"{args.char}: {response}")
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()