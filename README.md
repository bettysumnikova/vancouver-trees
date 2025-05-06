# Vancouver Trees Dashboard

The Vancouver Trees Dashboard is an interactive web application for exploring urban tree data by neighbourhoods. It supports both live data from the City of Vancouver’s public API and offline access using a local CSV file.

## Features

- Select data source: CSV file or API
- Choose a neighbourhood to display trees on an interactive map
- Filter trees by:
  - Common name (tree type)
  - Height range
  - Trunk diameter
  - Planting year
- Highlight a specific tree species and view a link to its Wikipedia page
- View summary statistics
- Visualize tree types and height ranges

## How to Run

1. Clone the repository:

```bash
git clone https://github.com/yourusername/vancouver-tree-dashboard.git
cd vancouver-tree-dashboard
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Launch the app:

```bash
streamlit run app.py
```

4. To use the CSV mode, ensure the file `public-trees.csv` is located in the root directory of the project.

## Technologies Used

- Streamlit
- Pandas
- Requests
- Folium
- streamlit-folium
- Altair

## Data Source

Public tree data provided by the City of Vancouver:  
[City of Vancouver - Public Trees Dataset](https://opendata.vancouver.ca/explore/dataset/public-trees/)
