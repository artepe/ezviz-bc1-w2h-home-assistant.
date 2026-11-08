"""Explicit connection policy. Unknown values never enable cloud access."""

def connection_mode(options):
    mode = options.get("connection_mode", "cloud")
    if mode not in ("local_only", "cloud"):
        raise ValueError("Choose Local only or EZVIZ cloud as the connection mode.")
    return mode
