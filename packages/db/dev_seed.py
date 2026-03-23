from packages.db.bootstrap import seed_minimal_dataset
from packages.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        ids = seed_minimal_dataset(session)
        print(
            "Seeded minimal dataset:",
            f"theme_id={ids['theme_id']}",
            f"document_id={ids['document_id']}",
            f"chunk_id={ids['chunk_id']}",
            f"thesis_id={ids['thesis_id']}",
            f"evidence_link_id={ids['evidence_link_id']}",
        )


if __name__ == "__main__":
    main()
