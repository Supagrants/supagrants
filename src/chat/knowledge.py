from phi.knowledge.pdf import PDFUrlKnowledgeBase
from phi.knowledge.text import TextKnowledgeBase
from phi.knowledge.combined import CombinedKnowledgeBase
from phi.vectordb.pgvector import PgVector
from config import POSTGRES_CONNECTION

pdf_knowledge_base = PDFUrlKnowledgeBase(
    urls=[],
    # Table name: ai.pdf_documents
    vector_db=PgVector(
        table_name="pdf_documents",
        db_url=POSTGRES_CONNECTION,
    ),
)

# text_knowledge_base = TextKnowledgeBase(
#     # Table name: ai.text_documents
#     vector_db=PgVector(
#         table_name="text_documents",
#         db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
#     ),
# )

knowledge_base = CombinedKnowledgeBase(
    sources=[
        pdf_knowledge_base,
    ],
    vector_db=PgVector(
        # Table name: ai.combined_documents
        table_name="combined_documents",
        db_url=POSTGRES_CONNECTION,
    ),
)


async def handle_document(file_info: dict):
    # if type add to vector space
    if file_info['mime_type'] == 'application/pdf':
        # blocking code
        pdf_knowledge_base.urls = [file_info['file_url']]
        pdf_knowledge_base.load(recreate=False)
    # acknowledge receipt
    return


async def handle_url(url: str, crawled_content: str):
    """
    Handle crawled URLs by adding their content to the TextKnowledgeBase in PostgreSQL.

    Args:
        url (str): The URL that was crawled.
        crawled_content (str): The content retrieved from crawling the URL.
    """
    # todo
    return