import os
from datetime import datetime
import json
import subprocess

# Configuration
OUTPUT_DIR = "/backup-data/web-ui/static/oled_log"
ITEMS_PER_PAGE = 50  # Number of files to show per page

def get_disk_labels(source_dir, destination_dir):
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
        src_mount = find_mount_point(source_dir)
        dst_mount = find_mount_point(destination_dir)
        
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
def get_file_data_json(source_dir, destination_dir):
    file_data = []
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        for file in files:
            src_file_path = os.path.join(root, file)
            dst_file_path = find_file_in_dst(file, destination_dir)
            file_data.append({
                'name': file,
                'source_path': f"{os.path.basename(source_dir)}/{os.path.relpath(src_file_path, source_dir)}",
                'source_disk': disk_labels['source'],
                'dest_path': f"{os.path.basename(destination_dir)}/{os.path.relpath(dst_file_path, destination_dir)}" if dst_file_path else None,
                'dest_disk': disk_labels['destination'] if dst_file_path else "N/A",
                'size': get_file_size_mb(src_file_path),
                'modified': get_file_mod_date(src_file_path),
                'status': 'Same' if dst_file_path else 'Missing'
            })
    
    # Convert to JSON string, escaping special characters
    json_str = json.dumps(file_data, indent=4).replace('</', '<\\/')
    return json_str

# Generate comparison report with the new template
def generate_comparison_report(source_dir, destination_dir, comparison_file):
    src_count, src_size = get_folder_stats(source_dir)
    dst_count, dst_size = get_folder_stats(destination_dir)
    
    # Get proper disk labels
    disk_labels = get_disk_labels(source_dir, destination_dir)  # Update this function too
    
    # Collect file data with correct labels
    file_data = []
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        for file in files:
            src_file_path = os.path.join(root, file)
            dst_file_path = find_file_in_dst(file, destination_dir)
            
            file_data.append({
                'name': file,
                'source_path': f"{os.path.basename(source_dir)}/{os.path.relpath(src_file_path, source_dir)}",
                'source_disk': disk_labels['source'],
                'dest_path': f"{os.path.basename(destination_dir)}/{os.path.relpath(dst_file_path, destination_dir)}" if dst_file_path else None,
                'dest_disk': disk_labels['destination'] if dst_file_path else "N/A",
                'size': get_file_size_mb(src_file_path),
                'modified': get_file_mod_date(src_file_path),
                'status': 'Same' if dst_file_path else 'Missing'
            })


    with open(comparison_file, "w", encoding='utf-8') as f:
        f.write(generate_html_template(
            title="[WebUI Backup]Comparison Report",
            src_count=src_count,
            src_size=src_size,
            dst_count=dst_count,
            dst_size=dst_size,
            file_data=file_data
        ))
# Keep your existing file list and maintenance functions
# Generate file list report

# Generate file list report with improved formatting and disk labels

# Generate file list report with improved formatting and disk labels
def generate_file_list(directory, output_file, title):
    print(f"Directory being processed: {directory}")
    directory = os.path.normpath(directory)
    file_count, size_gb = get_folder_stats(directory)
    location = "Source" if "src" in output_file.lower() else "Destination"
    
    # Get disk label for the directory
    disk_labels = get_disk_labels(directory, directory)  # Use same directory for both
    disk_label = disk_labels['source'] if "src" in output_file.lower() else disk_labels['destination']
    
    with open(output_file, "w", encoding='utf-8') as f:
        f.write(f"""<!DOCTYPE html>
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
        margin: 0;
    }}
    .header-card {{
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 20px;
        margin-bottom: 20px;
    }}
    .stats-row {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 15px;
        flex-wrap: wrap;
        gap: 15px;
    }}
    .stat-card {{
        background: #f8f9fa;
        border-radius: 6px;
        padding: 15px;
        flex: 1;
        min-width: 150px;
        text-align: center;
    }}
    .stat-value {{
        font-size: 1.5em;
        font-weight: bold;
        color: #2b5876;
        margin-bottom: 5px;
    }}
    .stat-label {{
        font-size: 0.9em;
        color: #666;
    }}
    .disk-label {{
        font-weight: bold;
        color: #2b5876;
        background: #e3f2fd;
        padding: 4px 8px;
        border-radius: 4px;
        margin-left: 8px;
        font-size: 0.9em;
    }}
    .controls-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
        padding: 0 10px;
        flex-wrap: wrap;
        gap: 15px;
    }}
    .date-toggle {{
        display: flex;
        align-items: center;
        gap: 8px;
        background: white;
        padding: 10px 15px;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-size: 0.9em;
        color: #555;
    }}
    .date-toggle input[type="checkbox"] {{
        width: 16px;
        height: 16px;
        cursor: pointer;
    }}
    .sort-controls {{
        display: flex;
        align-items: center;
        gap: 10px;
        background: white;
        padding: 10px 15px;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-size: 0.9em;
    }}
    .sort-btn {{
        padding: 6px 12px;
        border: 1px solid #ddd;
        background: white;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.85em;
        transition: all 0.2s;
    }}
    .sort-btn:hover {{
        background: #f0f0f0;
    }}
    .sort-btn.active {{
        background: #2b5876;
        color: white;
        border-color: #2b5876;
    }}
    .sort-direction {{
        margin-left: 5px;
        font-size: 0.8em;
    }}
    .file-table-container {{
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        overflow: hidden;
        margin-bottom: 20px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
    }}
    th {{
        background-color: #2b5876;
        color: white;
        padding: 12px 15px;
        text-align: left;
        font-weight: 600;
        cursor: pointer;
        user-select: none;
        position: relative;
    }}
    th:hover {{
        background-color: #1e3d59;
    }}
    td {{
        padding: 12px 15px;
        border-bottom: 1px solid #e0e0e0;
    }}
    tr:nth-child(even) {{
        background-color: #f8f9fa;
    }}
    tr:hover {{
        background-color: #e3f2fd;
        transition: background-color 0.2s;
    }}
    .file-name {{
        font-weight: 500;
        color: #333;
    }}
    .file-location {{
        color: #666;
        font-family: monospace;
        font-size: 0.9em;
    }}
    .file-size {{
        text-align: right;
        font-weight: 500;
        color: #2e7d32;
    }}
    .file-date {{
        color: #666;
        font-size: 0.85em;
        white-space: nowrap;
    }}
    .nav-buttons {{
        position: fixed;
        right: 20px;
        bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        z-index: 1000;
    }}
    .nav-button {{
        padding: 12px 16px;
        background: #2b5876;
        color: white;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        font-size: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        width: 50px;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .nav-button:hover {{
        background: #1e3d59;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    .page-title {{
        color: #333;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
    }}
    .sort-indicator {{
        margin-left: 5px;
        font-size: 0.8em;
    }}
    @media (max-width: 768px) {{
        th, td {{
            padding: 8px 10px;
            font-size: 14px;
        }}
        .stats-row {{
            flex-direction: column;
        }}
        .stat-card {{
            min-width: auto;
        }}
        .nav-button {{
            width: 45px;
            height: 45px;
            font-size: 14px;
        }}
        .date-toggle, .sort-controls {{
            font-size: 0.85em;
            padding: 8px 12px;
        }}
        .controls-row {{
            flex-direction: column;
            align-items: stretch;
        }}
        .sort-controls {{
            justify-content: center;
        }}
    }}
    @media (max-width: 480px) {{
        body {{
            padding: 5px;
        }}
        th, td {{
            padding: 6px 8px;
            font-size: 12px;
        }}
        .header-card {{
            padding: 15px;
        }}
    }}
</style>
</head>
<body>

<!-- Header Card -->
<div class="header-card">
    <div class="page-title">
        <h2 style="margin: 0; color: #333;">{title}</h2>
        <span class="disk-label">{disk_label}</span>
    </div>
    
    <div class="stats-row">
        <div class="stat-card">
            <div class="stat-value">{file_count}</div>
            <div class="stat-label">Total Files</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{size_gb}</div>
            <div class="stat-label">Total Size (GB)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{location}</div>
            <div class="stat-label">Location</div>
        </div>
    </div>
</div>

<!-- Controls Row -->
<div class="controls-row">
    <div class="date-toggle">
        <input type="checkbox" id="showDate" onchange="toggleDateColumn()">
        <label for="showDate">Show Modification Date</label>
    </div>
    <div class="sort-controls">
        <span>Sort by:</span>
        <button class="sort-btn active" onclick="sortTable('name', 'asc')" id="sort-name">
            Name <span class="sort-direction" id="name-dir">↑</span>
        </button>
        <button class="sort-btn" onclick="sortTable('date', 'desc')" id="sort-date">
            Date <span class="sort-direction" id="date-dir">↓</span>
        </button>
        <button class="sort-btn" onclick="sortTable('size', 'desc')" id="sort-size">
            Size <span class="sort-direction" id="size-dir"></span>
        </button>
    </div>
</div>

<!-- File Table -->
<div class="file-table-container">
    <table id="fileTable">
        <thead>
            <tr>
                <th onclick="sortTable('name', toggleDirection('name'))">File Name <span class="sort-indicator" id="th-name"></span></th>
                <th onclick="sortTable('location', toggleDirection('location'))">Location <span class="sort-indicator" id="th-location"></span></th>
                <th onclick="sortTable('size', toggleDirection('size'))" style="text-align: right;">Size (MB) <span class="sort-indicator" id="th-size"></span></th>
                <th class="date-column" style="display: none;" onclick="sortTable('date', toggleDirection('date'))">Modified <span class="sort-indicator" id="th-date"></span></th>
            </tr>
        </thead>
        <tbody id="fileTableBody">
""")
        
        # Collect all files first for consistent formatting
        all_files = []
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, directory)
                file_name = os.path.basename(file_path)
                file_location = os.path.dirname(rel_path) if os.path.dirname(rel_path) not in ["", "."] else os.path.basename(directory)
                file_size = get_file_size_mb(file_path)
                file_date = get_file_mod_date(file_path)  # This returns "YYYY-MM-DD HH:MM:SS"
                # Convert to timestamp for sorting
                file_timestamp = datetime.strptime(file_date, "%Y-%m-%d %H:%M:%S").timestamp() if file_date else 0
                all_files.append((file_name, file_location, file_size, file_date, file_timestamp))
        
        # Sort by name initially
        all_files.sort(key=lambda x: x[0].lower())
        
        # Write files to table
        for file_name, file_location, file_size, file_date, file_timestamp in all_files:
            size_display = f"{file_size:.2f}" if file_size >= 0.01 else "0.00"
            f.write(f"""
            <tr data-name="{file_name.lower()}" data-location="{file_location.lower()}" data-size="{file_size}" data-date="{file_timestamp}">
                <td class="file-name">{file_name}</td>
                <td class="file-location">{file_location}</td>
                <td class="file-size">{size_display}</td>
                <td class="file-date date-column" style="display: none;">{file_date}</td>
            </tr>
""")
        
        f.write("""
        </tbody>
    </table>
</div>

<!-- Navigation Buttons -->
<div class="nav-buttons">
    <button class="nav-button" onclick="scrollToTop()" title="Go to Top">↑</button>
    <button class="nav-button" onclick="scrollToBottom()" title="Go to Bottom">↓</button>
</div>

<script>
// Current sort state
let currentSort = { field: 'name', direction: 'asc' };
let fileData = [];

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function toggleDateColumn() {
    const showDate = document.getElementById('showDate').checked;
    const dateColumns = document.querySelectorAll('.date-column');
    
    dateColumns.forEach(column => {
        column.style.display = showDate ? 'table-cell' : 'none';
    });
    
    // Store preference in localStorage
    localStorage.setItem('showFileDates', showDate);
}

function toggleDirection(field) {
    if (currentSort.field === field) {
        return currentSort.direction === 'asc' ? 'desc' : 'asc';
    }
    return field === 'date' || field === 'size' ? 'desc' : 'asc';
}

function sortTable(field, direction) {
    currentSort = { field, direction };
    updateSortButtons();
    updateSortIndicators();
    
    const tbody = document.getElementById('fileTableBody');
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    rows.sort((a, b) => {
        let aValue, bValue;
        
        switch (field) {
            case 'name':
                aValue = a.getAttribute('data-name');
                bValue = b.getAttribute('data-name');
                return direction === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
                
            case 'location':
                aValue = a.getAttribute('data-location');
                bValue = b.getAttribute('data-location');
                return direction === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
                
            case 'size':
                aValue = parseFloat(a.getAttribute('data-size'));
                bValue = parseFloat(b.getAttribute('data-size'));
                return direction === 'asc' ? aValue - bValue : bValue - aValue;
                
            case 'date':
                aValue = parseFloat(a.getAttribute('data-date'));
                bValue = parseFloat(b.getAttribute('data-date'));
                return direction === 'asc' ? aValue - bValue : bValue - aValue;
        }
    });
    
    // Clear and re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));
}

function updateSortButtons() {
    // Update button active states
    document.getElementById('sort-name').classList.toggle('active', currentSort.field === 'name');
    document.getElementById('sort-date').classList.toggle('active', currentSort.field === 'date');
    document.getElementById('sort-size').classList.toggle('active', currentSort.field === 'size');
    
    // Update button directions
    document.getElementById('name-dir').textContent = currentSort.field === 'name' ? (currentSort.direction === 'asc' ? '↑' : '↓') : '';
    document.getElementById('date-dir').textContent = currentSort.field === 'date' ? (currentSort.direction === 'asc' ? '↑' : '↓') : '';
    document.getElementById('size-dir').textContent = currentSort.field === 'size' ? (currentSort.direction === 'asc' ? '↑' : '↓') : '';
}

function updateSortIndicators() {
    // Clear all indicators
    document.getElementById('th-name').textContent = '';
    document.getElementById('th-location').textContent = '';
    document.getElementById('th-size').textContent = '';
    document.getElementById('th-date').textContent = '';
    
    // Set current sort indicator
    const indicator = currentSort.direction === 'asc' ? '↑' : '↓';
    document.getElementById(`th-${currentSort.field}`).textContent = indicator;
}

// Load saved preference
window.addEventListener('load', function() {
    const savedPreference = localStorage.getItem('showFileDates');
    if (savedPreference === 'true') {
        document.getElementById('showDate').checked = true;
        toggleDateColumn();
    }
    
    // Initialize sort
    updateSortButtons();
    updateSortIndicators();
});

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.key === 'Home' || (e.ctrlKey && e.key === 'ArrowUp')) {
        scrollToTop();
    } else if (e.key === 'End' || (e.ctrlKey && e.key === 'ArrowDown')) {
        scrollToBottom();
    }
});
</script>

</body>
</html>
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
def generate_reports(source_dir, destination_dir):
    source_dir = os.path.normpath(source_dir)
    destination_dir = os.path.normpath(destination_dir)
    DATE_TIME = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR = '/backup-data/web-ui/static/oled_log'  # Ensure this path is correct
    
    COMPARISON_FILE = os.path.join(OUTPUT_DIR, f"{DATE_TIME}_comparison.html")
    SRC_FILE = os.path.join(OUTPUT_DIR, f"{DATE_TIME}_src.html")
    DST_FILE = os.path.join(OUTPUT_DIR, f"{DATE_TIME}_dst.html")

    # Generate reports with dynamic paths
    generate_comparison_report(source_dir, destination_dir, COMPARISON_FILE)
    generate_file_list(source_dir, SRC_FILE, f"[WebUI Backup]Files in {os.path.basename(source_dir)}")
    generate_file_list(destination_dir, DST_FILE, f"[WebUI Backup]Files in {os.path.basename(destination_dir)}")

    # Maintain report limit
    maintain_report_limit(OUTPUT_DIR)
    
    print("Reports generated:")
    print(f"- {COMPARISON_FILE}")
    print(f"- {SRC_FILE}")
    print(f"- {DST_FILE}")

if __name__ == "__main__":
    import json  # Add this at the top of your file
    generate_reports()
