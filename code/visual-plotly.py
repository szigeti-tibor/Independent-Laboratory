import json
import networkx as nx
import plotly.graph_objects as go
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

parent_dir = os.path.dirname(current_dir)

sub_folder = 'KEP_Survey_Experimentation_Instances'
file_name = 'uk_2019_splitpra_bandxmatch_pra0_pdd_0.05_50_0.json'

json_path = os.path.join(parent_dir, sub_folder, file_name)

def visualize_with_plotly(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    donors = data.get('data', {})
    G = nx.DiGraph()
    
    for d_id, info in donors.items():
        G.add_node(d_id, altruistic=info.get('altruistic', False))
        for match in info.get('matches', []):
            if str(match['recipient']) in donors:
                G.add_edge(d_id, str(match['recipient']))

    # Elrendezés számítása
    pos = nx.spring_layout(G, k=0.5)

    # Élek kirajzolása
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.5, color='#888'),
                            hoverinfo='none', mode='lines')

    # Csomópontok kirajzolása
    node_x = []
    node_y = []
    node_text = []
    node_color = []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        is_altruistic = G.nodes[node]['altruistic']
        node_text.append(f"ID: {node}<br>Altruista: {is_altruistic}")
        node_color.append('lightgreen' if is_altruistic else 'skyblue')

    node_trace = go.Scatter(x=node_x, y=node_y, mode='markers', hoverinfo='text',
                            marker=dict(showscale=False, color=node_color, size=15,
                                        line_width=2), text=node_text)

    # Ábra összeállítása
    fig = go.Figure(data=[edge_trace, node_trace],
                 layout=go.Layout(
                    title='Vese-csere hálózat (Plotly)',
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )
    
    fig.show()

visualize_with_plotly(json_path)