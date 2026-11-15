
from mcp.server import MCPServer

HOST = "127.0.0.1"
PORT = 8001

mcp = MCPServer(
    "Documents MCP Server",
    version="1.0.0",
    instructions="Read-only project document tools."
)


# =====================================================
# SERVICE LAYER
# =====================================================

DOCUMENTS = {
    "doc-001": {
        "title": "Project Alpha Budget",
        "content": (
            "Project Alpha has an approved "
            "budget of 5000 USD."
        )
    },
    "doc-002": {
        "title": "Project Beta Budget",
        "content": (
            "Project Beta has an approved "
            "budget of 12000 USD."
        )
    },
    "doc-003": {
        "title": "Engineering Policy",
        "content": (
            "All project changes require "
            "technical review."
        )
    }
}


class DocumentService:

    @staticmethod
    def search(query: str) -> list[dict]:

        query = query.strip().lower()

        if not query:
            return []

        results = []

        for doc_id, document in DOCUMENTS.items():

            searchable = (
                document["title"] + " " +
                document["content"]
            ).lower()

            if query in searchable:
                results.append({
                    "id": doc_id,
                    "title": document["title"]
                })

        return results

    @staticmethod
    def read(document_id: str) -> dict:

        document = DOCUMENTS.get(document_id)

        if not document:
            raise ValueError(
                f"Document not found: {document_id}"
            )

        return {
            "id": document_id,
            **document
        }


# =====================================================
# MCP TOOLS
# =====================================================

@mcp.tool()
def search_documents(query: str) -> list[dict]:
    """Search project documents by keyword."""
    return DocumentService.search(query)


@mcp.tool()
def read_document(document_id: str) -> dict:
    """Read a document using its document ID."""
    return DocumentService.read(document_id)


# =====================================================
# MCP RESOURCE
# =====================================================

@mcp.resource(
    "documents://catalog",
    mime_type="text/plain"
)
def document_catalog() -> str:
    """Return available document titles."""

    return "\n".join(
        f"{doc_id}: {doc['title']}"
        for doc_id, doc in DOCUMENTS.items()
    )


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        stateless_http=True,
        json_response=True
    )
