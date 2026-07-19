"""Split any oversized code chunks further, with overlap, so embeddings stay
within a reasonable token budget."""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.ingestion.parser import CodeChunk

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.MAX_CHUNK_CHARS,
    chunk_overlap=settings.CHUNK_OVERLAP,
    separators=["\n\n", "\n", " ", ""],
)


def split_oversized(chunk: CodeChunk) -> list[CodeChunk]:
    if len(chunk.text) <= settings.MAX_CHUNK_CHARS:
        return [chunk]

    pieces = _splitter.split_text(chunk.text)
    out = []
    for i, piece in enumerate(pieces):
        out.append(CodeChunk(
            file_path=chunk.file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            symbol=f"{chunk.symbol} (part {i + 1})" if chunk.symbol else None,
            node_type=chunk.node_type,
            text=piece,
        ))
    return out
