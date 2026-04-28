import json
import networkx as nx
from pyvis.network import Network
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

parent_dir = os.path.dirname(current_dir)

sub_folder = 'KEP_Survey_Experimentation_Instances'
file_name = 'uk_2019_splitpra_bandxmatch_pra0_pdd_0.05_50_0.json'

json_path = os.path.join(parent_dir, sub_folder, file_name)

def visualize_with_pyvis(json_file):
    with open(json_file, 'r') as f:
        content = json.load(f)
    
    donors = content.get('data', {})
    
    # Pyvis hálózat létrehozása (sötét mód és fizikai motor bekapcsolva)
    net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', directed=True)
    
    # Csomópontok és élek hozzáadása
    for donor_id, info in donors.items():
        is_altruistic = info.get('altruistic', False)
        color = '#97c2fc' if not is_altruistic else '#39ff14' # Kék a pároknak, Neon zöld az NDD-knek
        label = f"Donor/Pair {donor_id}" if not is_altruistic else f"NDD {donor_id}"
        
        net.add_node(donor_id, label=label, color=color, title=f"Vércsoport: {info.get('bloodtype')}")

    for donor_id, info in donors.items():
        for match in info.get('matches', []):
            recipient_id = str(match['recipient'])
            if recipient_id in donors:
                net.add_edge(donor_id, recipient_id, value=1)

    # Fizikai beállítások, hogy ne tapadjanak össze a csomópontok
    net.barnes_hut()
    net.show_buttons(filter_=['physics']) # Opcionális: beállítások panel a HTML-ben
    
    output_dir = os.path.join(current_dir, 'out')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, "kidney_graph_pyvis.html")
    net.save_graph(output_path)
    print(f"Kész! A fájlok az 'out' mappába kerültek: {output_path}")

visualize_with_pyvis(json_path)