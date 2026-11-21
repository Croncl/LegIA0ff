"""
MCP Transparência CGU & CNPJ (R9+) — Integração completa via mcp.ai REST API.

Ferramentas incluídas (6 no total):
- Transparência CGU:
  1. transparencia_despesas_documentos
  2. transparencia_despesas_favorecido
  3. transparencia_pep
  4. transparencia_sancoes
- CNPJ:
  5. cnpj_consultar
  6. cnpj_processos
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from dotenv import load_dotenv

import requests
from langchain_core.tools import tool, ToolException

# URLs Base oficiais
_BASE_URL_TRANSPARENCIA = "https://api.mcp.ai/api/transparencia"
_BASE_URL_CNPJ = "https://api.mcp.ai/api/cnpj"
_TIMEOUT = 120

# Carrega o .env da raiz do projeto
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _chamar(base_url: str, endpoint: str, payload: dict) -> dict:
    """Função centralizada para chamadas REST aos MCPs com autenticação padronizada."""
    api_key = os.getenv("MCP_AI_KEY", "")
    if not api_key:
        return {"erro": f"MCP_AI_KEY não configurada no .env (verificado em: {ENV_PATH})"}
    
    url = f"{base_url}/{endpoint}"

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )
        
        if not resp.ok:
            return {"erro": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return {"erro": f"O servidor retornou um conteúdo não-JSON. Resposta: {resp.text[:300]}"}
            
        return data.get("result", data)
        
    except requests.exceptions.Timeout:
        return {"erro": f"A requisição excedeu o tempo limite de {_TIMEOUT} segundos."}
    except requests.exceptions.ConnectionError:
        return {"erro": "Falha de conexão com o servidor."}
    except Exception as e:
        return {"erro": str(e)}


# ==========================================
# 1. FERRAMENTAS DE TRANSPARÊNCIA (CGU)
# ==========================================

@tool
def transparencia_despesas_documentos(cpf_cnpj: str, ano: int = 2024, fase: str = "pagamento", ordenacao: int = 2, pagina: int = 1) -> str:
    """Documentos de despesa (Empenho, Liquidação ou Pagamento) emitidos pelo Governo Federal para um favorecido.
    
    Args:
        cpf_cnpj: CPF ou CNPJ do favorecido.
        ano: Ano de emissão (AAAA). Default 2024.
        fase: 'empenho', 'liquidacao' ou 'pagamento'. Default 'pagamento'.
        ordenacao: 1=valor asc, 2=valor desc, 3=data asc, 4=data desc.
        pagina: Número da página (1-based).
    """
    payload = {
        "cpf_cnpj": cpf_cnpj,
        "ano": ano,
        "fase": fase,
        "ordenacao": ordenacao,
        "pagina": pagina
    }
    resultado = _chamar(_BASE_URL_TRANSPARENCIA, "despesas/documentos", payload)
    if "erro" in resultado:
        raise ToolException(resultado["erro"])
    
    documentos = resultado.get("documentos", [])
    if not documentos:
        return f"{cpf_cnpj}: sem documentos encontrados em {ano} ({fase})."
        
    linhas = [f"{cpf_cnpj} — Documentos de Despesa ({fase.upper()}) em {ano}:"]
    for doc in documentos[:10]:
        val_raw = doc.get('valor', 0)
        try:
            # Converte string monetária/numérica para float com segurança
            if isinstance(val_raw, str):
                val_limpo = val_raw.replace("R$", "").replace(".", "").replace(",", ".").strip()
                val_float = float(val_limpo)
            else:
                val_float = float(val_raw)
            valor_fmt = f"R$ {val_float:,.2f}"
        except (ValueError, TypeError):
            valor_fmt = str(val_raw)

        linhas.append(
            f"  - Data: {doc.get('data', '?')} | Órgão: {doc.get('orgao', '?')} | Valor: {valor_fmt}"
        )
    return "\n".join(linhas)


@tool
def transparencia_despesas_favorecido(cpf_cnpj: str, mes_ano_inicio: str = None, mes_ano_fim: str = None) -> str:
    """DESPESAS recebidas por uma empresa ou pessoa do Governo Federal num período ('quanto recebeu da União').
    
    Args:
        cpf_cnpj: CPF ou CNPJ do favorecido.
        mes_ano_inicio: Início no formato MM/AAAA.
        mes_ano_fim: Fim no formato MM/AAAA.
    """
    payload = {"cpf_cnpj": cpf_cnpj}
    if mes_ano_inicio:
        payload["mes_ano_inicio"] = mes_ano_inicio
    if mes_ano_fim:
        payload["mes_ano_fim"] = mes_ano_fim

    resultado = _chamar(_BASE_URL_TRANSPARENCIA, "despesas/favorecido", payload)
    if "erro" in resultado:
        raise ToolException(resultado["erro"])
    
    total = resultado.get("total", 0)
    if not total:
        return f"{cpf_cnpj}: sem despesas registradas no período."
        
    linhas = [f"{cpf_cnpj} — Total recebido da União: R$ {total:,.2f}"]
    for org in resultado.get("por_orgao", [])[:5]:
        linhas.append(f"  - {org.get('orgao', '?')}: R$ {org.get('valor', 0):,.2f}")
    return "\n".join(linhas)


@tool
def transparencia_pep(cpf: str) -> str:
    """Verifica se um CPF é de Pessoa Exposta Politicamente (PEP) e retorna função/órgão/período.
    
    Args:
        cpf: CPF (11 dígitos), com ou sem máscara.
    """
    resultado = _chamar(_BASE_URL_TRANSPARENCIA, "pep", {"cpf": cpf})
    if "erro" in resultado:
        raise ToolException(resultado["erro"])
    if not resultado.get("pep"):
        return f"{cpf}: não consta como Pessoa Exposta Politicamente."
        
    linhas = [f"{cpf}: PEP CONFIRMADO"]
    for p in resultado.get("vinculos", []):
        linhas.append(
            f"  - {p.get('funcao', '?')} — {p.get('orgao', '?')} "
            f"({p.get('data_inicio', '?')} a {p.get('data_fim', 'atual')})"
        )
    return "\n".join(linhas)


@tool
def transparencia_sancoes(cpf_cnpj: str) -> str:
    """Consulta sanções de uma pessoa ou empresa no Portal da Transparência (CEIS, CNEP, CEPIM).
    
    Args:
        cpf_cnpj: CPF ou CNPJ do sancionado.
    """
    resultado = _chamar(_BASE_URL_TRANSPARENCIA, "sancoes", {"cpf_cnpj": cpf_cnpj})
    if "erro" in resultado:
        raise ToolException(resultado["erro"])
        
    tem = resultado.get("tem_sancao", False)
    if not tem:
        return f"{cpf_cnpj}: sem sanções registradas (CEIS/CNEP/CEPIM)."
        
    linhas = [f"{cpf_cnpj}: SANÇÕES ENCONTRADAS"]
    for s in resultado.get("sancoes", []):
        linhas.append(
            f"  - {s.get('tipo', '?')} | {s.get('orgao_sancionador', '?')} | "
            f"Vigência: {s.get('data_inicio', '?')} a {s.get('data_fim', 'indefinida')}"
        )
    return "\n".join(linhas)


# ==========================================
# 2. FERRAMENTAS DE CNPJ
# ==========================================

@tool
def cnpj_consultar(cnpj: str) -> str:
    """Consulta cadastral de um CNPJ: razão social, nome fantasia, situação cadastral, CNAE, porte, QSA.
    
    Args:
        cnpj: CNPJ (14 dígitos), com ou sem máscara.
    """
    resultado = _chamar(_BASE_URL_CNPJ, "consultar", {"cnpj": cnpj})
    if "erro" in resultado:
        return f"Erro na consulta do CNPJ: {resultado['erro']}"
    
    razao = resultado.get("razao_social", "Não informada")
    fantasia = resultado.get("nome_fantasia", "-")
    situacao = resultado.get("situacao_cadastral", "Desconhecida")
    cnae = resultado.get("cnae_principal", "?")
    porte = resultado.get("porte", "?")
    municipio = resultado.get("municipio", "?")
    uf = resultado.get("uf", "?")
    
    linhas = [
        f"CNPJ: {cnpj}",
        f"Razão Social: {razao}",
        f"Nome Fantasia: {fantasia}",
        f"Situação: {situacao} | Porte: {porte} | CNAE: {cnae}",
        f"Local: {municipio}/{uf}",
        "--- Quadro de Sócios (QSA): ---"
    ]
    
    socios = resultado.get("socios", [])
    if not socios:
        linhas.append("  Nenhum sócio listado.")
    else:
        for s in socios:
            linhas.append(f"  - {s.get('nome', '?')} ({s.get('qualificacao', 'Sócio/Administrador')})")
            
    return "\n".join(linhas)


@tool
def cnpj_processos(cnpj: str, incluir_socios: bool = False) -> str:
    """Busca processos judiciais por NOME no Diário (DJEN) a partir do CNPJ e opcionalmente dos sócios.
    
    Args:
        cnpj: CNPJ (14 dígitos), com ou sem máscara.
        incluir_socios: Se true, também busca os processos de cada sócio. Default false.
    """
    resultado = _chamar(_BASE_URL_CNPJ, "processos", {"cnpj": cnpj, "incluir_socios": incluir_socios})
    if "erro" in resultado:
        return f"Ocorreu um erro ao consultar os processos: {resultado['erro']}"
    
    processos = resultado.get("processos", [])
    empresa = resultado.get("razao_social", cnpj)
    
    if not processos:
        return f"Nenhum processo judicial encontrado para {empresa} (CNPJ: {cnpj})."
        
    linhas = [f"Processos Judiciais encontrados para {empresa}:"]
    for p in processos[:10]:
        linhas.append(
            f"  - Processo: {p.get('numero_processo', 'N/D')} | Órgão: {p.get('orgao', 'N/D')} | "
            f"Parte: {p.get('parte', 'N/D')} ({p.get('tipo_envolvimento', 'N/D')})"
        )
    return "\n".join(linhas)


def criar_ferramentas_transparencia() -> list:
    """Retorna todas as 6 ferramentas configuradas (Transparência CGU + CNPJ)."""
    return [
        transparencia_despesas_documentos,
        transparencia_despesas_favorecido,
        transparencia_pep,
        transparencia_sancoes,
        cnpj_consultar,
        cnpj_processos
    ]