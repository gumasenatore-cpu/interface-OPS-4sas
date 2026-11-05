import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Cores Institucionais 4SAS
COLOR_FAVORAVEL = "#2E7D32"  # Verde Operacional
COLOR_ATENCAO = "#7F8C8D"    # Cinza Avaliação Técnica
COLOR_NOGO = "#F32735"       # Vermelho Não Operacional
COLOR_TEXT = "#0A192F"

def gerar_grafico_matriz_operacional_moderna(df_heatmap: pd.DataFrame, figsize=(5.5, 2.2), dpi=200) -> io.BytesIO:
    """
    Gera o gráfico moderno da Matriz Operacional em estilo Timeline.
    Retorna um buffer BytesIO em memória.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    color_map = {0: COLOR_FAVORAVEL, 1: COLOR_ATENCAO, 2: COLOR_NOGO}
    num_params = len(df_heatmap.index)
    num_hours = len(df_heatmap.columns)
    
    for y_idx, param in enumerate(df_heatmap.index):
        row_values = df_heatmap.iloc[y_idx].values
        start_idx = 0
        current_val = row_values[0]
        
        for x_idx in range(1, num_hours + 1):
            if x_idx == num_hours or row_values[x_idx] != current_val:
                ax.barh(
                    y=y_idx,
                    width=(x_idx - start_idx),
                    left=start_idx,
                    height=0.6,
                    color=color_map.get(current_val, COLOR_ATENCAO),
                    edgecolor='white',
                    linewidth=1.2
                )
                if x_idx < num_hours:
                    start_idx = x_idx
                    current_val = row_values[x_idx]

    ax.set_yticks(np.arange(num_params))
    ax.set_yticklabels(df_heatmap.index, fontsize=7, fontweight='bold', color=COLOR_TEXT)
    
    step = max(1, num_hours // 12)
    xticks_pos = np.arange(0, num_hours, step)
    xticks_labels = [f"{df_heatmap.columns[i]:02d}h" if isinstance(df_heatmap.columns[i], (int, np.integer)) else str(df_heatmap.columns[i]) for i in xticks_pos]
    
    ax.set_xticks(xticks_pos)
    ax.set_xticklabels(xticks_labels, fontsize=6, color=COLOR_TEXT)
    ax.set_xlim(-0.5, num_hours - 0.5)
    
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_visible(False)
        
    ax.tick_params(left=False, bottom=False)
    ax.grid(axis='x', linestyle=':', alpha=0.4, color='#CBD5E1')
    ax.set_title("Janela Operacional por Parâmetro (Timeline Go / No-Go)", fontsize=7.5, fontweight='bold', color=COLOR_TEXT, pad=8)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf