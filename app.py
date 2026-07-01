from core.query import ask

def main():
    print("=== GH05T3 Phase One: Badass Ingestion Online ===")

    while True:
        q = input("\nAsk GH05T3 ? ")
        if q.strip().lower() in ["exit", "quit"]:
            print("Exiting.")
            break

        response = ask(q)
        print("\nResponse:\n")
        print(response)

if __name__ == "__main__":
    main()
