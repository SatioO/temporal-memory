class KV:
    sessions = "mem:sessions"
    profiles = "mem:profiles"
    memories = "mem:memories",

    @staticmethod
    def observations(session_id: str) -> str:
        return f"mem:obs:{session_id}"

    @staticmethod
    def embeddings(obs_id: str) -> str:
        return f"mem:emb:{obs_id}"
