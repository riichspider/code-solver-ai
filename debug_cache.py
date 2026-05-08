from pathlib import Path
import os
import tempfile
from utils.smart_cache_v3 import create_smart_cache_v3
from utils.smart_cache_v3 import SmartCacheV3, ModelInfo, ValidationStatus
import sys
sys.path.append('.')

# Criar cache temporário com parâmetros padrão
temp_dir = Path(tempfile.mkdtemp())
cache = create_smart_cache_v3(directory=temp_dir)
print(f"Cache criado em: {temp_dir}")

# Parâmetros do teste
problem = "Test problem"
model_info = ModelInfo(name="qwen2.5-coder", version="latest")
language = "python"
mode = "fast"
validation_error = "SyntaxError: invalid syntax"
validation_status = ValidationStatus.FAILED
context_text = "Some context"

print("=== Teste de Cache Failure ===")
print(f"Problem: {problem}")
print(f"Model: {model_info.get_full_identifier()}")
print(f"Language: {language}")
print(f"Mode: {mode}")
print(f"Validation Error: {validation_error}")
print(f"Context: {context_text}")

# Gerar hashes para debug
problem_hash = cache.build_problem_hash(problem)
context_hash = cache.build_context_hash(context_text)
error_hash = cache.build_validation_error_hash(validation_error)

print(f"\nHashes:")
print(f"Problem hash: {problem_hash}")
print(f"Context hash: {context_hash}")
print(f"Error hash: {error_hash}")

# Gerar chave
key_set = cache.key_builder.build_failure_key(
    problem_hash=problem_hash,
    model_version=model_info.get_full_identifier(),
    language=language,
    mode=mode,
    context_hash=context_hash,
    validation_error_hash=error_hash
)

print(f"\nChave gerada: {key_set}")

# Definir falha
print("\nDefinindo falha...")
cache.set_failure(
    problem=problem,
    model_info=model_info,
    language=language,
    mode=mode,
    validation_error=validation_error,
    validation_status=validation_status,
    context_text=context_text
)

# Tentar obter falha
print("Obtendo falha...")
result = cache.get_failure(
    problem=problem,
    model_info=model_info,
    language=language,
    mode=mode,
    validation_error=validation_error,
    context_text=context_text
)

print(f"Resultado: {result}")

# Debug adicional: verificar diretamente no cache
print("\n=== Debug direto no cache ===")
direct_result = cache._get_from_cache(key_set)
print(f"Resultado direto com chave: {direct_result}")

# Listar todas as chaves no cache
print("\n=== Listar todas as entradas ===")
try:
    import sqlite3
    db_path = temp_dir / "smart_cache_v3.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT key, entry_type FROM cache_entries")
        rows = cursor.fetchall()
        print(f"Total de entradas: {len(rows)}")
        for key, entry_type in rows:
            print(f"  Key: {key}, Type: {entry_type}")
except Exception as e:
    print(f"Erro ao listar entradas: {e}")

if result:
    print(f"Validation status: {result.validation_status}")
    print(f"Error message: {result.validation_error_message}")
else:
    print("FALHA: Resultado é None!")
