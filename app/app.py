import pandas as pd
import numpy as np
import os
from collections import defaultdict, Counter
import streamlit as st
from io import BytesIO

# === 1. Carregamento do arquivo CSV ===
st.title("Resultados do Prêmio Senge Jovem")

uploaded_file = st.file_uploader("Envie o arquivo de avaliações (.csv)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # === 2. Detectar blocos de avaliação com base nas colunas "Comentários:" ===
    comentarios_cols = [col for col in df.columns if col.startswith("Comentários:")]
    comentarios_idxs = [df.columns.get_loc(col) for col in comentarios_cols]
    project_ranges = []

    start_idx = df.columns.get_loc("Categoria do Projeto") + 1
    for idx in comentarios_idxs:
        end_idx = idx
        project_ranges.append((start_idx, end_idx))
        start_idx = end_idx + 1

    # === 3. Inicializar estruturas ===
    avaliacoes_por_projeto = defaultdict(list)
    nomes_projetos = defaultdict(list)

    # === 4. Processar cada linha do DataFrame ===
    for _, linha in df.iterrows():
        categoria = linha["Categoria do Projeto"]
        for i, (start, end) in enumerate(project_ranges):
            bloco = linha.iloc[start:end+1]
            colunas_bloco = df.columns[start:end+1]

            # Nome do projeto
            nome_cols = [col for col in colunas_bloco if "nome do projeto" in col.lower()]
            nome_projeto = str(bloco[nome_cols[0]]).strip() if nome_cols else f"Projeto {i+1}"

            # Notas
            notas = pd.to_numeric(bloco, errors='coerce')
            nota_final = notas.mean() if not notas.isnull().all() else 0

            if nota_final == 0:
                continue  # Pular se não foi avaliado

            # Igualdade de Gênero
            col_genero = [col for col in colunas_bloco if "igualdade de gênero" in col.lower()]
            igualdade_genero = bloco[col_genero[0]] if col_genero else "não"
            resposta = str(igualdade_genero).strip().lower()
            tem_bonus = resposta == "sim"
            nota_com_bonus = nota_final * 1.1 if tem_bonus else nota_final

            # Cálculo da média do Mérito do Trabalho (4 critérios)
            col_clareza = [col for col in colunas_bloco if "clareza" in col.lower()]
            col_relevancia = [col for col in colunas_bloco if "relevância" in col.lower()]
            col_organizacao = [col for col in colunas_bloco if "organização" in col.lower()]
            col_resultados = [col for col in colunas_bloco if "resultados" in col.lower()]
            try:
                nota_clareza = float(bloco[col_clareza[0]])
                nota_relevancia = float(bloco[col_relevancia[0]])
                nota_organizacao = float(bloco[col_organizacao[0]])
                nota_resultados = float(bloco[col_resultados[0]])
                merito_medio = np.mean([nota_clareza, nota_relevancia, nota_organizacao, nota_resultados])
            except:
                merito_medio = np.nan

            chave = (categoria, i)
            avaliacoes_por_projeto[chave].append((nota_final, resposta, nota_com_bonus, merito_medio))
            nomes_projetos[chave].append(nome_projeto)

    # === 5. Calcular médias e montar resultados ===
    projetos = []

    for (categoria, bloco_idx), avaliacoes in avaliacoes_por_projeto.items():
        if not avaliacoes:
            continue

        notas_com_bonus = [a[2] for a in avaliacoes]
        respostas = [a[1] for a in avaliacoes]
        meritos = [a[3] for a in avaliacoes if not np.isnan(a[3])]

        nota_final_media = np.mean(notas_com_bonus)
        merito_final = np.mean(meritos) if meritos else np.nan

        # Contagem de votos Sim/Não
        contagem = Counter(respostas)
        desempate_str = []
        if contagem["sim"] > 0:
            desempate_str.append(f"{contagem['sim']} Sim")
        if contagem["não"] > 0:
            desempate_str.append(f"{contagem['não']} Não")
        desempate_final = " / ".join(desempate_str)

        # Nome mais comum
        nomes = [nome for nome in nomes_projetos[(categoria, bloco_idx)] if nome]
        nome_projeto_final = Counter(nomes).most_common(1)[0][0] if nomes else f"{categoria} {bloco_idx+1}"

        projetos.append({
            "Projeto Original": nome_projeto_final,
            "Categoria": categoria,
            "Índice Bloco": bloco_idx,
            "Nota com bônus": round(nota_final_media, 2),
            "Média Mérito do Trabalho": round(merito_final, 2) if not np.isnan(merito_final) else "-",
            "Desempate (Sim/Não)": desempate_final,
            "Número de Avaliações": len(avaliacoes)
        })

    # === 6. Criar DataFrame com numeração dos projetos respeitando a ordem original ===
    df_resultado = pd.DataFrame(projetos)
    df_resultado["Projeto"] = ""

    for categoria in df_resultado["Categoria"].unique():
        df_cat = df_resultado[df_resultado["Categoria"] == categoria]
        df_cat = df_cat.sort_values("Índice Bloco")
        for i, idx in enumerate(df_cat.index):
            numero = i + 1
            df_resultado.at[idx, "Projeto"] = f"Projeto {numero:02d}"

    # === 7. Reorganizar colunas e ajustar índice para começar em 1 ===
    colunas_ordem = ["Projeto", "Categoria", "Nota com bônus", "Média Mérito do Trabalho", "Desempate (Sim/Não)", "Número de Avaliações"]
    df_resultado = df_resultado[colunas_ordem]
    df_ordenado = df_resultado.sort_values(by=["Categoria", "Projeto"]).reset_index(drop=True)
    df_ordenado.index += 1  # <-- Aqui garantimos que o índice começa em 1

    # === 8. Gerar lista de avaliadores por categoria ===
    avaliadores_df = df[["Nome Completo", "Categoria do Projeto"]].drop_duplicates()
    avaliadores_df.columns = ["Nome", "Categoria"]

    avaliadores_por_categoria = (
        avaliadores_df.groupby("Categoria")["Nome"]
        .apply(lambda nomes: "\n".join(sorted(nomes)))
        .reset_index()
        .rename(columns={"Nome": "Avaliadores"})
    )

    # === 9. Exibir no app ===
    for categoria in df_ordenado["Categoria"].unique():
        st.subheader(f"📚 {categoria}")
        # Avaliadores
        aval_cat = avaliadores_por_categoria[avaliadores_por_categoria["Categoria"] == categoria]
        if not aval_cat.empty:
            st.markdown("*Avaliadores:*")
            st.text(aval_cat["Avaliadores"].values[0])
        # Projetos da categoria
        df_cat = df_ordenado[df_ordenado["Categoria"] == categoria].drop(columns=["Categoria"])
        st.dataframe(df_cat, use_container_width=True)

    # === 10. Gerar botão de download do Excel ===
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=True, sheet_name="Resultado")
        return output.getvalue()

    st.download_button(
        label="📥 Baixar resultado em Excel",
        data=to_excel(df_ordenado),
        file_name="Resultados_Avaliacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
