import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from gerador_pdf_boletim import gerar_pdf_boletim_reportlab

def testar_geracao_pdf_local():
    print("⏳ A gerar dados fictícios para teste...")
    
    # 1. Criar DataFrame fictício de 72 horas
    datas = [datetime.now() + timedelta(hours=i) for i in range(72)]
    df_dados = pd.DataFrame({
        'Data_Hora': datas,
        'Onda_ECMWF(m)': np.random.uniform(0.8, 2.2, 72),
        'Onda_WW3(m)': np.random.uniform(0.7, 2.0, 72),
        'Onda_Consenso(m)': np.random.uniform(0.9, 2.1, 72),
        'Onda_Dir': ['SE'] * 72,
        'Vento_ECMWF_Nos': np.random.uniform(10, 25, 72),
        'Vento_GFS_Nos': np.random.uniform(8, 22, 72),
        'Vento_ICON_Nos': np.random.uniform(9, 24, 72),
        'Vento_Consenso_Nos': np.random.uniform(10, 23, 72),
        'Vento_Dir': ['NE'] * 72,
        'Mare_Altura(m)': np.sin(np.linspace(0, 10 * np.pi, 72)) + 1.2,
        'Fase_Estuario': ['Enchente' if i % 2 == 0 else 'Vazante' for i in range(72)],
        'Corrente_Vel_Nos': np.random.uniform(0.2, 1.8, 72),
        'Corrente_Dir': ['S'] * 72,
        'Status': ['FAVORAVEL' if i % 3 != 0 else 'SEM OPERACAO' for i in range(72)]
    })

    # 2. Criar matriz heatmap (Kanban) fictícia (linhas: parâmetros, colunas: horas)
    df_heatmap = pd.DataFrame(
        np.random.choice([0, 1, 2], size=(3, 24)),
        index=['Onda (Hs)', 'Vento', 'Corrente'],
        columns=list(range(24))
    )

    # 3. Chamar a função refatorada
    print("📄 A compilar o PDF com o ReportLab...")
    pdf_bytes = gerar_pdf_boletim_reportlab(
        dataframe=df_dados,
        local_nome="Barra do Furado",
        dias_janela=3,
        favoraveis=45,
        tecnicas=15,
        nogo=12,
        df_heatmap=df_heatmap,
        lat=-22.16,
        lon=-41.13,
        equipamentos=["Kongsberg EA440", "Emlid Reach RS3"],
        limite_onda=1.5,
        limite_vento=18.0,
        limite_corrente=1.2,
        data_emissao=datetime.now().strftime("%d/%m/%Y %H:%M UTC")
    )

    # 4. Gravar em disco para inspeção visual
    nome_ficheiro_saida = "boletim_teste_local.pdf"
    with open(nome_ficheiro_saida, "wb") as f:
        f.write(pdf_bytes)

    print(f"✅ PDF gerado com sucesso: {nome_ficheiro_saida}")

if __name__ == "__main__":
    testar_geracao_pdf_local()