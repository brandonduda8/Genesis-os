import os

class GitHubConfig:
    @staticmethod
    def token():
        token = os.getenv("GITHUB_TOKEN")

        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN environment variable not set."
            )

        return token
