from src.fetcher import fetch_latest_news
from src.summarizer import summarize_with_ai
from src.telegram import send_telegram_message


def main():
    articles = fetch_latest_news()
    summary = summarize_with_ai(articles)
    send_telegram_message(summary)


if __name__ == "__main__":
    main()
