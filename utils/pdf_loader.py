import pdfplumber
from pypdf import PdfReader
from typing import List, Dict
import io


class PDFLoader:
    """Extract text content from PDF files using pdfplumber and pypdf."""

    def __init__(self):
        self.supported_formats = ["pdf"]

    def extract_with_pdfplumber(self, file) -> str:
        """Extract text using pdfplumber (better for tables and complex layouts)."""
        try:
            with pdfplumber.open(file) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row:
                                filtered = [str(cell) if cell else "" for cell in row]
                                text_parts.append(" | ".join(filtered))

                return "\n\n".join(text_parts)
        except Exception as e:
            return f"[Error pdfplumber: {str(e)}]"

    def extract_with_pypdf(self, file) -> str:
        """Extract text using pypdf (fallback for encrypted or complex PDFs)."""
        try:
            reader = PdfReader(file)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts)
        except Exception as e:
            return f"[Error pypdf: {str(e)}]"

    def extract_text(self, file) -> str:
        """Extract text from a PDF, trying pdfplumber first then pypdf."""
        text = self.extract_with_pdfplumber(file)

        if not text or text.startswith("[Error") or len(text.strip()) < 10:
            file.seek(0)
            text = self.extract_with_pypdf(file)

        return text.strip() if text else ""

    def extract_metadata(self, file) -> Dict:
        """Extract basic metadata from a PDF."""
        try:
            reader = PdfReader(file)
            metadata = reader.metadata
            return {
                "pages": len(reader.pages),
                "title": str(metadata.title) if metadata and metadata.title else "Sin titulo",
                "author": str(metadata.author) if metadata and metadata.author else "Desconocido",
                "subject": str(metadata.subject) if metadata and metadata.subject else "",
            }
        except Exception:
            return {"pages": 0, "title": "Sin titulo", "author": "Desconocido", "subject": ""}

    def extract_all_pdfs(self, uploaded_files: list) -> List[Dict]:
        """Extract text from multiple uploaded PDF files."""
        results = []

        for file in uploaded_files:
            text = self.extract_text(file)
            file.seek(0)
            metadata = self.extract_metadata(file)
            file.seek(0)

            chunks = self._chunk_text(text, chunk_size=500)

            results.append({
                "filename": file.name,
                "metadata": metadata,
                "full_text": text,
                "chunks": chunks,
            })

        return results

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[Dict]:
        """Split extracted text into chunks for embedding."""
        if not text or len(text.strip()) < 10:
            return []

        chunks = []
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        current_chunk = ""
        part_idx = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append({"text": current_chunk, "part": part_idx})
                    part_idx += 1
                current_chunk = para

        if current_chunk:
            chunks.append({"text": current_chunk, "part": part_idx})

        return chunks

    def pdfs_to_dataframe(self, uploaded_files: list) -> List[Dict]:
        """Convert multiple PDFs to a list of chunk dictionaries for RAG indexing."""
        results = self.extract_all_pdfs(uploaded_files)
        all_chunks = []

        for result in results:
            for chunk in result["chunks"]:
                all_chunks.append({
                    "id": f"pdf_{result['filename']}_{chunk['part']}",
                    "text": chunk["text"],
                    "metadata": {
                        "source": "pdf",
                        "filename": result["filename"],
                        "pages": result["metadata"]["pages"],
                        "part": chunk["part"],
                    },
                })

        return all_chunks
