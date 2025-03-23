import os
from datetime import datetime

# Configuration
SRC_DIR = "/mnt/src"
DST_DIR = "/mnt/dst/just-backup"
OUTPUT_DIR = "/backup-data/web-ui/static/oled_log"

# Helper function to generate HTML header
def generate_html_header(title):
    header = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    table {{width: 100%; border-collapse: collapse;}}
    th, td {{padding: 8px; text-align: left; border-bottom: 1px solid #ddd;}}
    th {{background-color: #f2f2f2;}} tr:hover {{background-color: #f5f5f5;}}
    .missing {{color: orange;}} .same {{ color: green; }}
    .nav-button {{margin: 5px; cursor: pointer; padding: 10px; border: none; background-color: #007bff; color: white; border-radius: 5px;}}
    .nav-button {{position: fixed; right: 20px; z-index: 1000;}}
    #topBtn {{bottom: 60px;}} #bottomBtn {{bottom: 20px;}}
    @media (max-width: 600px) {{th, td {{padding: 4px; font-size: 12px;}}}}
    .hidden {{display: none;}} /* Initially hide optional columns */
</style>
<script>
function scrollToTop() {{
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}

function scrollToBottom() {{
    window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
}}

function filterTable(status) {{
    var table, tr, td, i;
    table = document.querySelector('table');
    tr = table.getElementsByTagName('tr');
    
    for (i = 1; i < tr.length; i++) {{
        td = tr[i].getElementsByTagName('td')[5]; // Status column
        if (td) {{
            if (status === 'All') {{
                tr[i].style.display = ''; // Show all rows
            }} else {{
                tr[i].style.display = td.textContent.includes(status) ? '' : 'none';
            }}
        }}
    }}
}}

function toggleColumn(columnIndex, checkbox) {{
    var table = document.querySelector("table");
    var cells = table.querySelectorAll("tr td:nth-child(" + columnIndex + "), tr th:nth-child(" + columnIndex + ")");
    cells.forEach(cell => {{
        cell.classList.toggle("hidden", !checkbox.checked);
    }});
}}
</script>
</head>
<body>

<h2>{title}</h2>

<h3>Filters</h3>
<button class="filter-button" onclick="filterTable('All')">Show All</button>
<button class="filter-button" onclick="filterTable('Same')">Show Same</button>
<button class="filter-button" onclick="filterTable('Missing')">Show Missing</button>

<h3>Columns</h3>
<label><input type="checkbox" onclick="toggleColumn(2, this)"> Location in Source</label>
<label><input type="checkbox" onclick="toggleColumn(3, this)"> Location in Destination</label>
<label><input type="checkbox" onclick="toggleColumn(5, this)"> Size of File (MB)</label>

<button class="nav-button" id="topBtn" onclick="scrollToTop()">Go to Top</button>
<button class="nav-button" id="bottomBtn" onclick="scrollToBottom()">Go to Bottom</button>

<table border="1">
<tr>
    <th>Name</th>
    <th class="hidden">Location in Source</th>
    <th class="hidden">Location in Destination</th>
    <th>Date of File</th>
    <th class="hidden">Size of File (MB)</th>
    <th>Status</th>
</tr>
"""
    return header

# Helper function to generate HTML footer
def generate_html_footer():
    return "</table></body></html>"

# Helper function to get file size in MB
def get_file_size_mb(file_path):
    return round(os.path.getsize(file_path) / (1024 * 1024), 2)

# Helper function to get file modification date
def get_file_mod_date(file_path):
    return datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")

# Helper function to recursively search for a file in the destination directory
def find_file_in_dst(file_name, dst_dir):
    for root, _, files in os.walk(dst_dir):
        if file_name in files:
            return os.path.join(root, file_name)
    return None

# Generate comparison report
def generate_comparison_report(comparison_file):
    with open(comparison_file, "w") as f:
        f.write(f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    th {{ background-color: #f2f2f2; }} tr:hover {{ background-color: #f5f5f5; }}
    .missing {{ color: orange; }} .same {{ color: green; }}
    .nav-button {{ margin: 5px; cursor: pointer; padding: 10px; border: none; background-color: #007bff; color: white; border-radius: 5px; }}
    .nav-button {{ position: fixed; right: 20px; z-index: 1000; }}
    #topBtn {{ bottom: 60px; }} #bottomBtn {{ bottom: 20px; }}
    @media (max-width: 600px) {{ th, td {{ padding: 4px; font-size: 12px; }} }}
    /* Hide optional columns by default */
    .col-src, .col-dst, .col-size {{ display: none; }}
</style>
<script>
function scrollToTop() {{
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}

function scrollToBottom() {{
    window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
}}

function filterTable(status) {{
    var table = document.querySelector('table');
    var tr = table.getElementsByTagName('tr');
    for (var i = 1; i < tr.length; i++) {{
        var td = tr[i].getElementsByTagName('td')[5]; // Status column (6th column)
        if (td) {{
            if (status === 'All') {{
                tr[i].style.display = '';
            }} else {{
                tr[i].style.display = td.textContent.includes(status) ? '' : 'none';
            }}
        }}
    }}
}}

function toggleColumn(columnClass, checkbox) {{
    var cells = document.getElementsByClassName(columnClass);
    for (var i = 0; i < cells.length; i++) {{
        cells[i].style.display = checkbox.checked ? 'table-cell' : 'none';
    }}
}}
</script>
</head>
<body>
<h2>[Just Copy]Comparison Report</h2>
<h3>Filters</h3>
<button class="filter-button" onclick="filterTable('All')">Show All</button>
<button class="filter-button" onclick="filterTable('Same')">Show Same</button>
<button class="filter-button" onclick="filterTable('Missing')">Show Missing</button>
<h3>Columns</h3>
<label><input type="checkbox" onclick="toggleColumn('col-src', this)"> Source Path</label>
<label><input type="checkbox" onclick="toggleColumn('col-dst', this)"> Dest. Path</label>
<label><input type="checkbox" onclick="toggleColumn('col-size', this)"> File Size</label>
<button class="nav-button" id="topBtn" onclick="scrollToTop()">Go to Top</button>
<button class="nav-button" id="bottomBtn" onclick="scrollToBottom()">Go to Bottom</button>
<table border="1">
<tr>
    <th>Name</th>
    <th class="col-src">Source Path</th>
    <th class="col-dst">Dest. Path</th>
    <th>Date of File</th>
    <th class="col-size">File Size </th>
    <th>Status</th>
</tr>
""")
        # Compare files in the source directory
        for root, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]
            files.sort() 
            for file in files:
                src_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_file_path, SRC_DIR)
                dst_file_path = find_file_in_dst(file, DST_DIR)
                
                src_size = get_file_size_mb(src_file_path)
                src_date = get_file_mod_date(src_file_path)
                dst_rel_path = os.path.relpath(dst_file_path, DST_DIR) if dst_file_path else "N/A"
                
                if dst_file_path:
                    status = "Same"
                else:
                    status = "Missing"
                
                status_class = "same" if status == "Same" else "missing"
                f.write(f"""
<tr>
    <td>{file}</td>
    <td class="col-src">{rel_path}</td>
    <td class="col-dst">{dst_rel_path}</td>
    <td>{src_date}</td>
    <td class="col-size">{src_size}</td>
    <td class='{status_class}'>{status}</td>
</tr>
""")
        f.write("</table></body></html>")

# Generate file list report
def generate_file_list(directory, output_file, title):
    with open(output_file, "w") as f:
        f.write(f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    th {{ background-color: #f2f2f2; }}
    @media (max-width: 600px) {{ th, td {{ padding: 4px; font-size: 12px; }} }}
</style>
</head>
<body>
<h2>{title}</h2>
<table border="1">
<tr>
    <th>Name</th>
    <th>Location</th>
    <th>Size of File (MB)</th>
</tr>
""")
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]
            files.sort() 
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, directory)
                file_name = os.path.basename(file_path)
                # Use 'root' if file is in the base directory
                file_location = os.path.dirname(rel_path) if os.path.dirname(rel_path) not in ["", "."] else "root"
                file_size = get_file_size_mb(file_path)
                f.write(f"""
<tr>
    <td>{file_name}</td>
    <td>{file_location}</td>
    <td>{file_size}</td>
</tr>
""")
        f.write("</table></body></html>")

# Function to maintain only the last 10 reports of each type
def maintain_report_limit(directory, limit=10):
    report_types = ["comparison.html", "src.html", "dst.html"]
    for report_type in report_types:
        files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(report_type)]
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        for file in files[limit:]:
            os.remove(file)

# Function to generate all reports
def generate_reports():
    DATE_TIME = datetime.now().strftime("%Y%m%d_%H%M%S")
    COMPARISON_FILE = os.path.join(OUTPUT_DIR, f"{DATE_TIME}_comparison.html")
    SRC_FILE = os.path.join(OUTPUT_DIR, f"{DATE_TIME}_src.html")
    DST_FILE = os.path.join(OUTPUT_DIR, f"{DATE_TIME}_dst.html")

    # Generate reports
    generate_comparison_report(COMPARISON_FILE)
    generate_file_list(SRC_DIR, SRC_FILE, f"[Just Copy]Files in {SRC_DIR}")
    generate_file_list(DST_DIR, DST_FILE, f"[Just Copy]Files in {DST_DIR}")

    # Maintain only the last 10 reports
    maintain_report_limit(OUTPUT_DIR)

    print("Reports generated:")
    print(f"- {COMPARISON_FILE}")
    print(f"- {SRC_FILE}")
    print(f"- {DST_FILE}")

if __name__ == "__main__":
    generate_reports()
