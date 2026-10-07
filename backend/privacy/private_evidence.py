import os


def private_snapshot_path(event_id: str) -> str:
    if not event_id or os.path.basename(event_id) != event_id:
        raise ValueError("Invalid event ID")

    media_dir = os.path.abspath(os.getenv("MEDIA_DIR", "./media"))
    private_dir = os.path.abspath(
        os.getenv(
            "PRIVATE_EVIDENCE_DIR",
            os.path.join(os.path.dirname(media_dir), "private_evidence"),
        )
    )
    if os.path.commonpath((media_dir, private_dir)) == media_dir:
        raise ValueError("Private evidence directory must be outside MEDIA_DIR")

    return os.path.join(private_dir, f"{event_id}.jpg")
