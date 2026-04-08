def test_openai():
    import os
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import SystemMessage, UserMessage
    from azure.core.credentials import AzureKeyCredential

    endpoint = "https://models.github.ai/inference"

    from dotenv import load_dotenv
    load_dotenv()

    model = os.getenv("GITHUB_MODEL", "openai/gpt-4o")

    token = os.environ["GITHUB_TOKEN"]

    client = ChatCompletionsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(token),
    )

    response = client.complete(
        messages=[
            SystemMessage("You are a helpful assistant."),
            UserMessage("What is the capital of France?"),
        ],
        model=model
    )

    print(response.choices[0].message.content)

def test_codeact():
    from src.codeact.codeact import CodeAct
    codeact = CodeAct()
    print(codeact.files.ls("."))

if __name__ == "__main__":
    test_codeact()