from gh05t3_train.ingest import ingest_corpus
from gh05t3_train.trainer import train_model


def main():
    samples = ingest_corpus()
    model, tokenizer = train_model(samples)
    return model, tokenizer


if __name__ == "__main__":
    main()
