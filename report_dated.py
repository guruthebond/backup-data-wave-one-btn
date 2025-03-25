import os
from datetime import datetime
import json
import subprocess

# Configuration
SRC_DIR = "/mnt/src"
DST_DIR = "/mnt/dst/dated-backup"
OUTPUT_DIR = "/backup-data/web-ui/static/oled_log"
ITEMS_PER_PAGE = 50  # Number of files to show per page

def get_disk_labels():
    """Get disk labels by mountpoint with proper source/destination mapping"""
    try:
        # Get all mounted filesystems with labels
        result = subprocess.run(
            ['lsblk', '-o', 'mountpoint,label', '-n', '-l', '-J'],
            capture_output=True,
            text=True,
            check=True
        )
        labels = {}
        lsblk_data = json.loads(result.stdout)
        
        # Create mapping of mountpoints to labels
        for device in lsblk_data.get('blockdevices', []):
            if 'mountpoint' in device and device['mountpoint']:
                label = device.get('label')
                if not label:
                    # If no label, use the mountpoint basename
                    label = os.path.basename(device['mountpoint'])
                labels[device['mountpoint']] = label
        
        # Find the specific mountpoints for our source and destination
        src_mount = find_mount_point(SRC_DIR)
        dst_mount = find_mount_point(DST_DIR)
        
        return {
            'source': labels.get(src_mount, "Source Disk"),
            'destination': labels.get(dst_mount, "Backup Disk")
        }
    except Exception as e:
        print(f"Warning: Could not get disk labels - {str(e)}")
        return {
            'source': "Source Disk",
            'destination': "Backup Disk"
        }

def find_mount_point(path):
    """Find the mount point for a given path"""
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        parent = os.path.dirname(path)
        if parent == path:
            return path
        path = parent
    return path

# Helper function to calculate folder statistics
def get_folder_stats(directory):
    file_count = 0
    total_size = 0  # in bytes
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        file_count += len(files)
        for file in files:
            file_path = os.path.join(root, file)
            total_size += os.path.getsize(file_path)
    
    size_gb = round(total_size / (1024 ** 3), 2)
    return file_count, size_gb

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


# New function to generate the HTML template with sorting and pagination
def generate_html_template(title, src_count, src_size, dst_count, dst_size, file_data):
    file_data_json = json.dumps(file_data, ensure_ascii=False).replace("</", "<\\/")
    total_pages = (len(file_data) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
    body {{
        font-family: Arial, sans-serif;
        padding: 10px;
        max-width: 100%;
        background-color: #f5f5f5;
    }}
    .header-card {{
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 15px;
        margin-bottom: 15px;
    }}
    .stats-row {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
    }}
    .file-card {{
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 15px;
        margin-bottom: 15px;
        overflow-x: auto;
    }}
    .file-name {{
        font-weight: bold;
        margin-bottom: 8px;
        word-break: break-all;
    }}
    .path-row {{
        display: flex;
        flex-direction: column;
        margin-bottom: 8px;
    }}
    .path-label {{
        font-size: 0.8em;
        color: #666;
        margin-bottom: 2px;
    }}
    .path-value {{
        font-family: monospace;
        font-size: 0.9em;
        word-break: break-all;
        padding: 5px;
        background: #f9f9f9;
        border-radius: 4px;
    }}
    .meta-row {{
        display: flex;
        justify-content: space-between;
        margin-top: 10px;
    }}
    .file-meta {{
        font-size: 0.9em;
        color: #666;
    }}
    .status {{
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: bold;
    }}
    .status-same {{
        background: #e6f7e6;
        color: #2e7d32;
    }}
    .status-missing {{
        background: #fff3e0;
        color: #e65100;
    }}
    .control-panel {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 15px 0;
    }}
    .filter-buttons {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }}
    .sort-options {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }}
    .control-btn {{
        padding: 8px 12px;
        background: #f0f0f0;
        border: none;
        border-radius: 20px;
        cursor: pointer;
        font-size: 0.9em;
        display: flex;
        align-items: center;
        gap: 5px;
    }}
    .control-btn.active {{
        background: #007bff;
        color: white;
    }}
    .sort-direction {{
        font-size: 0.8em;
        opacity: 0.7;
    }}
    .pagination {{
        display: flex;
        justify-content: center;
        gap: 5px;
        margin: 20px 0;
        flex-wrap: wrap;
    }}
    .page-btn {{
        padding: 8px 12px;
        background: #f0f0f0;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        min-width: 40px;
    }}
    .page-btn.active {{
        background: #007bff;
        color: white;
    }}
    .page-info {{
        padding: 8px 12px;
        text-align: center;
    }}
    .page-nav {{
        font-weight: bold;
    }}
    .disk-label {{
        font-weight: bold;
        color: #2b5876;
        background: #f0f4f8;
        padding: 2px 6px;
        border-radius: 4px;
        margin-right: 8px;
        font-size: 0.85em;
    }}
    .loading {{
        text-align: center;
        padding: 20px;
        color: #666;
    }}
    .error {{
        color: #dc3545;
    }}
    @media (max-width: 600px) {{
        .pagination {{
            gap: 3px;
        }}
        .page-btn {{
            padding: 6px 8px;
            min-width: 30px;
        }}
        .path-row {{
            flex-direction: column;
        }}
        .path-label {{
            margin-bottom: 5px;
        }}
    }}
    @media (min-width: 768px) {{
        .path-row {{
            flex-direction: row;
            align-items: center;
        }}
        .path-label {{
            flex: 0 0 80px;
            margin-bottom: 0;
        }}
        .control-panel {{
            justify-content: space-between;
        }}
    }}
</style>
</head>
<body>

<!-- Header Card -->
<div class="header-card">
    <h2>{title}</h2>
    <div class="stats-row">
        <div>
            <div style="font-size: 0.9em; color: #666;">Source</div>
            <strong>{src_count} files</strong> ({src_size} GB)
        </div>
        <div>
            <div style="font-size: 0.9em; color: #666;">Destination</div>
            <strong>{dst_count} files</strong> ({dst_size} GB)
        </div>
    </div>
</div>

<!-- Control Panel -->
<div class="control-panel">
    <div class="filter-buttons">
        <button class="control-btn active" onclick="filterFiles('all')">All Files</button>
        <button class="control-btn" onclick="filterFiles('same')">Same</button>
        <button class="control-btn" onclick="filterFiles('missing')">Missing</button>
    </div>
    
    <div class="sort-options">
        <button class="control-btn" onclick="sortFiles('name', 'asc')">
            Name <span class="sort-direction" id="name-sort-dir">↓</span>
        </button>
        <button class="control-btn" onclick="sortFiles('date', 'desc')">
            Date <span class="sort-direction" id="date-sort-dir">↓</span>
        </button>
    </div>
</div>

<!-- File Container -->
<div id="file-container">
    <div class="loading">Loading files...</div>
</div>

<!-- Pagination -->
<div class="pagination">
    <button class="page-btn page-nav" onclick="goToPage(1)">First</button>
    <button class="page-btn page-nav" onclick="prevPage()">Previous</button>
    
    <div id="page-numbers" style="display: flex; gap: 5px;">
        <!-- Page numbers will be inserted here by JavaScript -->
    </div>
    
    <button class="page-btn page-nav" onclick="nextPage()">Next</button>
    <button class="page-btn page-nav" onclick="goToPage({total_pages})">Last</button>
</div>
<div class="page-info" id="page-info">Page 1 of {total_pages}</div>

<script id="file-data" type="application/json">
{file_data_json}
</script>

<script>
// Current state
let currentPage = 1;
const itemsPerPage = {ITEMS_PER_PAGE};
let currentFilter = 'all';
let currentSort = {{ field: 'date', direction: 'desc' }};
let totalPages = {total_pages};
let allFiles = [];

// Initialize when page loads
window.onload = function() {{
    try {{
        // Load file data
        const dataElement = document.getElementById('file-data');
        if (!dataElement) {{
            showError('Data element not found');
            return;
        }}
        
        allFiles = JSON.parse(dataElement.textContent);
        if (!Array.isArray(allFiles)) {{
            showError('Invalid file data format');
            return;
        }}
        
        // Add timestamps for sorting
        allFiles = allFiles.map(file => ({{
            ...file,
            timestamp: new Date(file.modified.replace(' ', 'T')).getTime()
        }}));
        
        // Initial render
        totalPages = Math.ceil(allFiles.length / itemsPerPage);
        updateSortIndicators();
        renderFiles();
        
    }} catch (e) {{
        showError('Initialization failed: ' + e.message);
        console.error(e);
    }}
}};

function showError(message) {{
    const container = document.getElementById('file-container');
    if (container) {{
        container.innerHTML = '<div class="loading error">' + message + '</div>';
    }}
    console.error(message);
}}

// Main page navigation
function goToPage(page) {{
    page = parseInt(page);
    if (isNaN(page) || page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    
    if (page !== currentPage) {{
        currentPage = page;
        renderFiles();
        renderPageNumbers();
        updatePageInfo();
    }}
}}

function prevPage() {{ goToPage(currentPage - 1); }}
function nextPage() {{ goToPage(currentPage + 1); }}

function updatePageInfo() {{
    const infoElement = document.getElementById('page-info');
    if (infoElement) {{
        infoElement.textContent = `Page ${{currentPage}} of ${{totalPages}}`;
    }}
}}

// Render page numbers
function renderPageNumbers() {{
    const container = document.getElementById('page-numbers');
    if (!container) return;
    
    container.innerHTML = '';
    
    const maxVisible = 5;
    let start = Math.max(1, currentPage - Math.floor(maxVisible/2));
    let end = Math.min(totalPages, start + maxVisible - 1);
    
    // Adjust if we're at the end
    if (end - start + 1 < maxVisible) {{
        start = Math.max(1, end - maxVisible + 1);
    }}
    
    // First page and ellipsis
    if (start > 1) {{
        addPageButton(1);
        if (start > 2) {{
            container.appendChild(createEllipsis());
        }}
    }}
    
    // Middle pages
    for (let i = start; i <= end; i++) {{
        addPageButton(i);
    }}
    
    // Last page and ellipsis
    if (end < totalPages) {{
        if (end < totalPages - 1) {{
            container.appendChild(createEllipsis());
        }}
        addPageButton(totalPages);
    }}
}}

function createEllipsis() {{
    const ellipsis = document.createElement('span');
    ellipsis.textContent = '...';
    ellipsis.style.padding = '0 5px';
    return ellipsis;
}}

function addPageButton(page) {{
    const container = document.getElementById('page-numbers');
    if (!container) return;
    
    const btn = document.createElement('button');
    btn.className = 'page-btn' + (page === currentPage ? ' active' : '');
    btn.textContent = page;
    btn.onclick = function() {{ goToPage(page); }};
    container.appendChild(btn);
}}

// Sorting
function sortFiles(field, direction) {{
    if (currentSort.field === field) {{
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    }} else {{
        currentSort.field = field;
        currentSort.direction = direction || 'asc';
    }}
    
    updateSortIndicators();
    
    allFiles.sort((a, b) => {{
        let compare = field === 'name' 
            ? a.name.localeCompare(b.name) 
            : a.timestamp - b.timestamp;
        return currentSort.direction === 'asc' ? compare : -compare;
    }});
    
    currentPage = 1;
    renderFiles();
    renderPageNumbers();
}}

function updateSortIndicators() {{
    document.querySelectorAll('.sort-direction').forEach(el => {{
        el.textContent = '';
    }});
    const dirElement = document.getElementById(currentSort.field + '-sort-dir');
    if (dirElement) {{
        dirElement.textContent = currentSort.direction === 'asc' ? '↑' : '↓';
    }}
}}

// Filtering
function filterFiles(filter) {{
    currentFilter = filter;
    currentPage = 1;
    
    // Update button states
    document.querySelectorAll('.filter-buttons .control-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.textContent.toLowerCase().includes(filter));
    }});
    
    renderFiles();
    renderPageNumbers();
}}

// Main rendering function
function renderFiles() {{
    try {{
        const container = document.getElementById('file-container');
        if (!container) {{
            showError('File container not found');
            return;
        }}
        
        // Apply current filter
        const filteredFiles = allFiles.filter(file => {{
            if (currentFilter === 'all') return true;
            if (currentFilter === 'same') return file.status === 'Same';
            if (currentFilter === 'missing') return file.status === 'Missing';
            return true;
        }});
        
        // Update total pages
        totalPages = Math.ceil(filteredFiles.length / itemsPerPage);
        if (currentPage > totalPages) currentPage = Math.max(1, totalPages);
        
        // Get current page
        const startIdx = (currentPage - 1) * itemsPerPage;
        const pageFiles = filteredFiles.slice(startIdx, startIdx + itemsPerPage);
        
        updatePageInfo();
        
        // Render files
        container.innerHTML = '';
        
        if (pageFiles.length === 0) {{
            container.innerHTML = '<div class="loading">No files match current filter</div>';
            return;
        }}
        
        pageFiles.forEach(file => {{
            const card = document.createElement('div');
            card.className = 'file-card';
            
            const sizeDisplay = file.size.toLocaleString('en-US', {{ maximumFractionDigits: 2 }});
            const destPath = file.dest_path 
                ? `<span class="disk-label">${{file.dest_disk}}</span>${{file.dest_path}}` 
                : '<span style="color: #e65100;">Not found in destination</span>';
            
            card.innerHTML = `
                <div class="file-name">${{file.name}}</div>
                <div class="path-row">
                    <div class="path-label">Source:</div>
                    <div class="path-value">
                        <span class="disk-label">${{file.source_disk}}</span>
                        ${{file.source_path}}
                    </div>
                </div>
                <div class="path-row">
                    <div class="path-label">Dest:</div>
                    <div class="path-value">
                        ${{destPath}}
                    </div>
                </div>
                <div class="meta-row">
                    <div class="file-meta">Modified: ${{file.modified}} • ${{sizeDisplay}} MB</div>
                    <div class="status ${{file.status === 'Same' ? 'status-same' : 'status-missing'}}">
                        ${{file.status}}
                    </div>
                </div>
            `;
            container.appendChild(card);
        }});
        
    }} catch (e) {{
        showError('Error rendering files: ' + e.message);
        console.error(e);
    }}
}}
</script>

</body>
</html>
"""
# Helper function to generate JSON data of files
def get_file_data_json():
    file_data = []
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        for file in files:
            src_file_path = os.path.join(root, file)
            dst_file_path = find_file_in_dst(file, DST_DIR)
            
            file_data.append({
                'name': file,
                'source_path': os.path.relpath(src_file_path, SRC_DIR),
                'dest_path': os.path.relpath(dst_file_path, DST_DIR) if dst_file_path else None,
                'size': get_file_size_mb(src_file_path),
                'modified': get_file_mod_date(src_file_path),
                'status': 'Same' if dst_file_path else 'Missing'
            })
    
    # Convert to JSON string, escaping special characters
    json_str = json.dumps(file_data, indent=4).replace('</', '<\\/')
    return json_str

# Generate comparison report with the new template
def generate_comparison_report(comparison_file):
    src_count, src_size = get_folder_stats(SRC_DIR)
    dst_count, dst_size = get_folder_stats(DST_DIR)
    
    # Get proper disk labels
    disk_labels = get_disk_labels()
    
    # Collect file data with correct labels
    file_data = []
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        for file in files:
            src_file_path = os.path.join(root, file)
            dst_file_path = find_file_in_dst(file, DST_DIR)
            
            file_data.append({
                'name': file,
                'source_path': os.path.relpath(src_file_path, SRC_DIR),
                'source_disk': disk_labels['source'],
                'dest_path': os.path.relpath(dst_file_path, DST_DIR) if dst_file_path else None,
                'dest_disk': disk_labels['destination'] if dst_file_path else "N/A",
                'size': get_file_size_mb(src_file_path),
                'modified': get_file_mod_date(src_file_path),
                'status': 'Same' if dst_file_path else 'Missing'
            })


    with open(comparison_file, "w", encoding='utf-8') as f:
        f.write(generate_html_template(
            title="[Dated Copy]Comparison Report",
            src_count=src_count,
            src_size=src_size,
            dst_count=dst_count,
            dst_size=dst_size,
            file_data=file_data
        ))
# Keep your existing file list and maintenance functions
# Generate file list report
def generate_file_list(directory, output_file, title):
    file_count, size_gb = get_folder_stats(directory)
    location = "Source" if "src" in output_file.lower() else "Destination"
    
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
    .stats-table {{ width: 50%; margin-bottom: 20px; }}
    .file-table {{ margin-top: 20px; }}
    .nav-button {{ margin: 5px; cursor: pointer; padding: 10px; border: none; background-color: #007bff; color: white; border-radius: 5px; }}
    .nav-button {{ position: fixed; right: 20px; z-index: 1000; }}
    #topBtn {{ bottom: 60px; }} #bottomBtn {{ bottom: 20px; }}
</style>
<script>
function scrollToTop() {{
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}

function scrollToBottom() {{
    window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
}}

function filterTable(status) {{
    var tables = document.getElementsByClassName('file-table');
    for (var t = 0; t < tables.length; t++) {{
        var table = tables[t];
        var tr = table.getElementsByTagName('tr');
        for (var i = 1; i < tr.length; i++) {{
            var td = tr[i].getElementsByTagName('td')[2]; // Status column (3rd column)
            if (td) {{
                if (status === 'All') {{
                    tr[i].style.display = '';
                }} else {{
                    tr[i].style.display = td.textContent.includes(status) ? '' : 'none';
                }}
            }}
        }}
    }}
}}
</script>
</head>
<body>
<h2>{title}</h2>

<table class="stats-table">
<tr>
    <th>{location}</th>
    <th>Files Count</th>
    <th>Size (GB)</th>
</tr>
<tr>
    <td>{location}</td>
    <td>{file_count}</td>
    <td>{size_gb}</td>
</tr>
</table>

<table border="1" class="file-table">
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
        f.write("""
</table>
<button class="nav-button" id="topBtn" onclick="scrollToTop()">Go to Top</button>
<button class="nav-button" id="bottomBtn" onclick="scrollToBottom()">Go to Bottom</button>
</body></html>
""")

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
    generate_file_list(SRC_DIR, SRC_FILE, f"[Dated Copy]Files in {SRC_DIR}")
    generate_file_list(DST_DIR, DST_FILE, f"[Dated Copy]Files in {DST_DIR}")

    # Maintain only the last 10 reports
    maintain_report_limit(OUTPUT_DIR)

    print("Reports generated:")
    print(f"- {COMPARISON_FILE}")
    print(f"- {SRC_FILE}")
    print(f"- {DST_FILE}")

if __name__ == "__main__":
    import json  # Add this at the top of your file
    generate_reports()
