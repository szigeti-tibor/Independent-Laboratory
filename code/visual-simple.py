import json
import networkx as nx
import matplotlib.pyplot as plt
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

parent_dir = os.path.dirname(current_dir)

sub_folder = 'KEP_Survey_Experimentation_Instances'
file_name = 'uk_2019_splitpra_bandxmatch_pra0_pdd_0.05_50_0.json'

json_path = os.path.join(parent_dir, sub_folder, file_name)

def visualize_kidney_exchange(json_file):
    # JSON fájl betöltése
    with open(json_file, 'r') as f:
        content = json.load(f)
    
    donors = content.get('data', {})
    
    # Irányított gráf létrehozása
    G = nx.DiGraph()
    
    # Csúcsok hozzáadása és tulajdonságok beállítása
    for node_id, info in donors.items():
        is_altruistic = info.get('altruistic', False)
        # Megkülönböztetjük az altruista donorokat (NDD) és a párokat
        G.add_node(node_id, altruistic=is_altruistic)
        
    # Élek (potenciális cserék) hozzáadása
    for donor_id, info in donors.items():
        matches = info.get('matches', [])
        for match in matches:
            recipient_id = str(match['recipient'])
            # Csak akkor adjuk hozzá, ha a cél recipiens létezik a rendszerben
            if recipient_id in donors:
                G.add_edge(donor_id, recipient_id)

    # Megjelenítés beállításai
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, k=0.3, iterations=50) # Elrendezés algoritmusa
    
    # Csomópontok színezése (Kék: Párok, Zöld: Altruisták)
    node_colors = [
        'lightgreen' if G.nodes[n].get('altruistic') else 'skyblue' 
        for n in G.nodes
    ]
    
    # Gráf kirajzolása
    nx.draw(G, pos, 
            with_labels=True, 
            node_color=node_colors, 
            node_size=600, 
            edge_color='gray', 
            arrowsize=15, 
            font_size=8,
            alpha=0.8)
    
    plt.title(f"Vese-csere gráf: {json_file}")
    plt.show()

# Használat a kisebb fájllal
visualize_kidney_exchange(json_path)