import pandas as pd
from typing import List, Dict, Optional
import io


def load_csv(file) -> pd.DataFrame:
    """Load a CSV file uploaded via Streamlit into a DataFrame."""
    try:
        df = pd.read_csv(file)
        return df
    except UnicodeDecodeError:
        file.seek(0)
        df = pd.read_csv(file, encoding="latin-1")
        return df
    except Exception as e:
        raise ValueError(f"Error al leer el archivo CSV: {str(e)}")


def load_multiple_csvs(files: list) -> pd.DataFrame:
    """Load and merge multiple CSV files into a single DataFrame."""
    dataframes = []
    file_stats = []

    for file in files:
        try:
            df = load_csv(file)
            file_stats.append({"filename": file.name, "rows": len(df), "cols": len(df.columns), "columns": list(df.columns)})
            dataframes.append(df)
        except Exception as e:
            file_stats.append({"filename": file.name, "error": str(e)})

    if not dataframes:
        raise ValueError("Ningun archivo CSV pudo ser leido.")

    common_cols = set(dataframes[0].columns)
    for df in dataframes[1:]:
        common_cols = common_cols.intersection(set(df.columns))

    common_cols = sorted(common_cols)

    aligned_dfs = []
    for df in dataframes:
        aligned = df[[c for c in common_cols if c in df.columns]].copy()
        for col in common_cols:
            if col not in aligned.columns:
                aligned[col] = None
        aligned_dfs.append(aligned)

    merged = pd.concat(aligned_dfs, ignore_index=True)
    merged = merged.drop_duplicates()

    return merged, file_stats


def validate_csv(df: pd.DataFrame) -> Dict[str, any]:
    """Validate the CSV structure for knowledge base use."""
    result = {"valid": True, "errors": [], "warnings": [], "columns": list(df.columns)}

    if df.empty:
        result["valid"] = False
        result["errors"].append("El archivo CSV esta vacio.")
        return result

    text_columns = []
    for col in df.columns:
        non_null_ratio = df[col].notna().sum() / len(df)
        if non_null_ratio > 0.5:
            sample_val = str(df[col].dropna().iloc[0]) if not df[col].dropna().empty else ""
            if len(sample_val) > 20:
                text_columns.append(col)

    if not text_columns:
        result["warnings"].append(
            "No se detectaron columnas de texto largo. "
            "Se usaran todas las columnas como fuente de conocimiento."
        )
        text_columns = list(df.columns)

    result["text_columns"] = text_columns
    return result


def chunk_dataframe(df: pd.DataFrame, text_columns: Optional[List[str]] = None, chunk_size: int = 500, source_label: str = "csv") -> List[Dict]:
    """Convert DataFrame rows into text chunks for embedding."""
    chunks = []

    if text_columns is None:
        text_columns = [col for col in df.columns if not pd.api.types.is_numeric_dtype(df[col])]
        if not text_columns:
            text_columns = list(df.columns)

    for idx, row in df.iterrows():
        parts = []
        for col in text_columns:
            if col in row.index and pd.notna(row[col]):
                parts.append(f"{col}: {str(row[col])}")

        if not parts:
            continue

        full_text = "\n".join(parts)

        if len(full_text) <= chunk_size:
            chunks.append({
                "id": f"{source_label}_chunk_{idx}",
                "text": full_text,
                "metadata": {
                    "row": idx,
                    "columns": text_columns,
                    "source": source_label,
                },
            })
        else:
            sentences = full_text.replace("\n", ". ").split(". ")
            current_chunk = ""
            part_idx = 0

            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 2 > chunk_size and current_chunk:
                    chunks.append({
                        "id": f"{source_label}_chunk_{idx}_{part_idx}",
                        "text": current_chunk.strip(),
                        "metadata": {
                            "row": idx,
                            "columns": text_columns,
                            "source": source_label,
                        },
                    })
                    part_idx += 1
                    current_chunk = sentence + ". "
                else:
                    current_chunk += sentence + ". "

            if current_chunk.strip():
                chunks.append({
                    "id": f"{source_label}_chunk_{idx}_{part_idx}",
                    "text": current_chunk.strip(),
                    "metadata": {
                        "row": idx,
                        "columns": text_columns,
                        "source": source_label,
                    },
                })

    return chunks


def get_csv_summary(df: pd.DataFrame) -> str:
    """Generate a human-readable summary of the uploaded CSV."""
    n_rows = len(df)
    n_cols = len(df.columns)
    cols = ", ".join(df.columns.tolist())
    return f"Archivo cargado: {n_rows} registros, {n_cols} columnas ({cols})"
