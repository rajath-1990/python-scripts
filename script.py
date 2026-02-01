#!/usr/bin/env python3
"""
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime
import argparse
from collections import defaultdict


def detect_language(filename):
    """Detect programming language from file extension and name."""
    ext = Path(filename).suffix.lstrip('.')
    name_lower = filename.lower()
    
    #special handling for gradle files
    if '.gradle' in filename:
        if '.gradle.kts' in filename:
            return 'gradle-kotlin'
        return 'gradle'
    
    #special handling for properties files
    if filename.endswith('.properties'):
        return 'properties'
    
    #extension-based detection
    language_map = {
        'kt': 'kotlin', 'kts': 'kotlin', 'java': 'java',
        'gradle': 'gradle', 'pro': 'proguard', 'properties': 'properties',
        'json': 'json', 'yaml': 'yaml', 'yml': 'yaml',
        'aidl': 'aidl',
        'js': 'javascript', 'mjs': 'javascript', 'cjs': 'javascript',
        'ts': 'typescript', 'jsx': 'jsx', 'tsx': 'tsx',
        'html': 'html', 'htm': 'html', 'css': 'css',
        'scala': 'scala', 'groovy': 'groovy',
        'py': 'python', 'sh': 'bash', 'bash': 'bash',
        'md': 'markdown',
        'c': 'c', 'cpp': 'cpp', 'cc': 'cpp', 'cxx': 'cpp', 'h': 'cpp', 'hpp': 'cpp',
        'rb': 'ruby', 'go': 'go', 'rs': 'rust', 'php': 'php',
        'cs': 'csharp', 'sql': 'sql', 'vue': 'vue',
        'graphql': 'graphql', 'graphqls': 'graphql',
    }
    
    language = language_map.get(ext.lower(), 'unknown')
    
    #special handling for xml files
    if ext.lower() == 'xml':
        if 'androidmanifest' in name_lower:
            return 'android-manifest'
        elif 'layout' in str(filename) or '/res/' in str(filename) or '\\res\\' in str(filename):
            return 'android-xml'
        return 'xml'
    
    return language


#=============================================================================
#directory tree generation - ai-friendly project structure
#=============================================================================

def generate_directory_tree(files, base_path, max_depth=None):
    """
    Generate ASCII tree structure from processed files.
    Only shows directories that contain matched files.
    
    Args:
        files: list of Path objects (files that will be processed)
        base_path: Path to the root folder
        max_depth: maximum depth to display (None = unlimited)
    
    Returns:
        string containing ASCII tree representation
    """
    if not files:
        return ""
    
    #build directory structure from file paths
    #key: relative directory path, value: list of filenames
    dir_structure = defaultdict(list)
    
    for file_path in files:
        try:
            relative = file_path.relative_to(base_path)
            parent = str(relative.parent).replace('\\', '/')
            if parent == '.':
                parent = ''
            dir_structure[parent].append(relative.name)
        except ValueError:
            #file not under base_path
            dir_structure[''].append(file_path.name)
    
    #build tree structure
    tree_lines = []
    root_name = base_path.name or 'project'
    tree_lines.append(f"{root_name}/")
    
    #get all unique directory paths and sort them
    all_dirs = set()
    for dir_path in dir_structure.keys():
        if dir_path:
            parts = dir_path.split('/')
            for i in range(len(parts)):
                all_dirs.add('/'.join(parts[:i+1]))
    
    #sort directories for consistent output
    sorted_dirs = sorted(all_dirs)
    
    #track which directories we've already output
    output_dirs = set()
    
    def get_depth(path):
        """Get depth of a path."""
        if not path:
            return 0
        return len(path.split('/'))
    
    def get_prefix(depth, is_last_at_level):
        """Generate tree prefix based on depth and position."""
        if depth == 0:
            return ""
        
        prefix_parts = []
        for i in range(depth - 1):
            prefix_parts.append("│   ")
        
        if is_last_at_level:
            prefix_parts.append("└── ")
        else:
            prefix_parts.append("├── ")
        
        return ''.join(prefix_parts)
    
    def should_show_depth(depth):
        """Check if we should show this depth level."""
        if max_depth is None:
            return True
        return depth <= max_depth
    
    #collect all items (dirs and files) with their paths for proper ordering
    all_items = []
    
    #add directories
    for dir_path in sorted_dirs:
        depth = get_depth(dir_path)
        if should_show_depth(depth):
            all_items.append({
                'type': 'dir',
                'path': dir_path,
                'name': dir_path.split('/')[-1],
                'depth': depth,
                'parent': '/'.join(dir_path.split('/')[:-1]) if '/' in dir_path else ''
            })
    
    #add files
    for dir_path, filenames in dir_structure.items():
        depth = get_depth(dir_path) + 1 if dir_path else 1
        if should_show_depth(depth):
            for filename in sorted(filenames):
                all_items.append({
                    'type': 'file',
                    'path': f"{dir_path}/{filename}" if dir_path else filename,
                    'name': filename,
                    'depth': depth,
                    'parent': dir_path
                })
    
    #sort all items by path for proper tree ordering
    all_items.sort(key=lambda x: x['path'].lower())
    
    #group items by parent to determine last item at each level
    items_by_parent = defaultdict(list)
    for item in all_items:
        items_by_parent[item['parent']].append(item)
    
    #track ancestors' "is_last" status for proper prefix
    def build_tree_recursive(parent_path, ancestor_is_last):
        """Recursively build tree lines."""
        items = items_by_parent.get(parent_path, [])
        
        for idx, item in enumerate(items):
            is_last = (idx == len(items) - 1)
            depth = item['depth']
            
            #build prefix
            prefix_parts = []
            for i, was_last in enumerate(ancestor_is_last):
                if was_last:
                    prefix_parts.append("    ")
                else:
                    prefix_parts.append("│   ")
            
            if is_last:
                prefix_parts.append("└── ")
            else:
                prefix_parts.append("├── ")
            
            prefix = ''.join(prefix_parts)
            
            if item['type'] == 'dir':
                tree_lines.append(f"{prefix}{item['name']}/")
                #recurse into this directory
                build_tree_recursive(item['path'], ancestor_is_last + [is_last])
            else:
                tree_lines.append(f"{prefix}{item['name']}")
    
    #start building from root level
    build_tree_recursive('', [])
    
    return '\n'.join(tree_lines)


def create_project_structure_section(tree_content, file_count, total_dirs):
    """Create the XML project_structure section."""
    lines = [
        '  <project_structure>',
        f'    <summary files="{file_count}" directories="{total_dirs}"/>',
        '    <tree><![CDATA[',
        tree_content,
        '    ]]></tree>',
        '  </project_structure>',
    ]
    return '\n'.join(lines)


def count_directories(files, base_path):
    """Count unique directories containing the matched files."""
    dirs = set()
    for file_path in files:
        try:
            relative = file_path.relative_to(base_path)
            parent = str(relative.parent).replace('\\', '/')
            if parent != '.':
                #add all parent directories
                parts = parent.split('/')
                for i in range(len(parts)):
                    dirs.add('/'.join(parts[:i+1]))
        except ValueError:
            pass
    return len(dirs)


#=============================================================================
#compress mode functions - extract structural elements only
#=============================================================================

def compress_kotlin(content):
    """
    Extract structural elements from Kotlin code:
    - Package and imports (condensed)
    - Annotations (@HiltViewModel, @Module, @Inject, etc.)
    - Class/object/interface declarations with body preview
    - Enum entries
    - Sealed class subclasses
    - Companion object content
    - Function signatures with body preview
    - Property declarations (with types)
    - Init blocks (with structure preserved)
    """
    lines = content.split('\n')
    extracted = []
    in_multiline_comment = False
    brace_depth = 0
    in_init_block = False
    init_brace_depth = 0
    init_content = []
    
    #patterns for kotlin structural elements
    patterns = {
        'package': re.compile(r'^\s*package\s+[\w.]+'),
        'import': re.compile(r'^\s*import\s+'),
        'annotation': re.compile(r'^\s*@\w+'),
        'class': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+|internal\s+|open\s+|abstract\s+|sealed\s+|data\s+|enum\s+|annotation\s+|value\s+|inner\s+)*'
            r'(?:class|object)\s+(\w+)'
        ),
        'enum_class': re.compile(r'^\s*(?:public\s+|private\s+|internal\s+)*enum\s+class\s+(\w+)'),
        'sealed_class': re.compile(r'^\s*(?:public\s+|private\s+|internal\s+)*sealed\s+(?:class|interface)\s+(\w+)'),
        'interface': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+|internal\s+|sealed\s+|fun\s+)*'
            r'interface\s+(\w+)'
        ),
        'function': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+|internal\s+|open\s+|override\s+|suspend\s+|inline\s+|abstract\s+|final\s+|operator\s+|infix\s+|tailrec\s+|external\s+|actual\s+|expect\s+)*'
            r'fun\s+(?:<[^>]+>\s*)?(\w+)\s*\('
        ),
        'property': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+|internal\s+|open\s+|override\s+|abstract\s+|final\s+|const\s+|lateinit\s+|actual\s+|expect\s+)*'
            r'(?:val|var)\s+(\w+)'
        ),
        'companion': re.compile(r'^\s*companion\s+object'),
        'constructor': re.compile(r'^\s*(?:public\s+|private\s+|protected\s+|internal\s+)*constructor\s*\('),
        'init': re.compile(r'^\s*init\s*\{'),
        'typealias': re.compile(r'^\s*typealias\s+(\w+)'),
        #patterns for init block content we want to preserve
        'scope_launch': re.compile(r'^\s*(?:viewModelScope|lifecycleScope|CoroutineScope|GlobalScope)\s*\.\s*launch'),
        'flow_collect': re.compile(r'^\s*\w+.*\.collect\s*\{'),
        'use_case_invoke': re.compile(r'^\s*\w+.*\.invoke\s*\('),
        'when_statement': re.compile(r'^\s*when\s*\('),
        'when_branch': re.compile(r'^\s*is\s+\w+'),
        'state_update': re.compile(r'^\s*_\w+\s*[.=]'),
    }
    
    imports = []
    pending_annotations = []  #collect annotations to attach to next declaration
    processed_lines = set()  #track lines already processed
    
    for i, line in enumerate(lines):
        #skip already processed lines
        if i in processed_lines:
            continue
        
        stripped = line.strip()
        
        #handle multi-line comments
        if '/*' in stripped and '*/' not in stripped:
            in_multiline_comment = True
            continue
        if '*/' in stripped:
            in_multiline_comment = False
            continue
        if in_multiline_comment:
            continue
        
        #skip single-line comments and empty lines (except in init block)
        if not in_init_block and (stripped.startswith('//') or not stripped):
            continue
        
        #track brace depth
        open_braces = stripped.count('{')
        close_braces = stripped.count('}')
        
        #handle init block content
        if in_init_block:
            init_brace_depth += open_braces - close_braces
            
            #check if init block ended
            if init_brace_depth <= 0:
                in_init_block = False
                #add condensed init content
                extracted.append('    init {')
                extracted.extend(init_content)
                extracted.append('    }')
                init_content = []
                continue
            
            #preserve important patterns inside init
            if stripped and not stripped.startswith('//'):
                #scope launches
                if patterns['scope_launch'].match(stripped):
                    init_content.append(f'        {stripped}')
                    continue
                #flow collect
                if patterns['flow_collect'].match(stripped):
                    init_content.append(f'        {stripped}')
                    continue
                #use case invocations
                if patterns['use_case_invoke'].match(stripped):
                    init_content.append(f'        {stripped}')
                    continue
                #when statements
                if patterns['when_statement'].match(stripped):
                    init_content.append(f'        {stripped}')
                    continue
                #when branches (is NetworkResult.Success, etc.)
                if patterns['when_branch'].match(stripped):
                    init_content.append(f'            {stripped}')
                    continue
                #state updates (_property = value or _property.value = x)
                if patterns['state_update'].match(stripped):
                    #condense if too long
                    if len(stripped) > 60:
                        init_content.append(f'                {stripped[:55]}...')
                    else:
                        init_content.append(f'                {stripped}')
                    continue
            continue
        
        brace_depth += open_braces - close_braces
        
        #package declaration
        if patterns['package'].match(stripped):
            extracted.append(line)
            extracted.append('')
            continue
        
        #collect imports (will condense later)
        if patterns['import'].match(stripped):
            imports.append(stripped)
            continue
        
        #collect annotations - attach to next declaration
        if patterns['annotation'].match(stripped):
            #handle multi-line annotations like @Composable or @HiltViewModel
            annotation_line = line
            #check for multi-line annotation with parameters
            if '(' in stripped and ')' not in stripped:
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    annotation_line += '\n' + lines[j]
                    processed_lines.add(j)
                    j += 1
                if j < len(lines):
                    annotation_line += '\n' + lines[j]
                    processed_lines.add(j)
            pending_annotations.append(annotation_line)
            continue
        
        #enum class - capture entries
        if patterns['enum_class'].match(stripped):
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            
            extracted.append(line)
            processed_lines.add(i)
            
            #find and extract enum entries
            j = i + 1
            enum_brace_depth = open_braces - close_braces
            
            #find opening brace if not on same line
            while j < len(lines) and enum_brace_depth == 0:
                enum_line = lines[j].strip()
                if '{' in enum_line:
                    enum_brace_depth = 1
                    extracted.append(lines[j])
                    processed_lines.add(j)
                j += 1
            
            #extract enum entries (until ; or first function/property)
            while j < len(lines):
                enum_line = lines[j]
                enum_stripped = enum_line.strip()
                processed_lines.add(j)
                
                #stop at semicolon (end of entries)
                if enum_stripped == ';':
                    extracted.append(enum_line)
                    break
                
                #stop at function or property declaration
                if patterns['function'].match(enum_stripped) or patterns['property'].match(enum_stripped):
                    break
                
                #capture enum entry
                if enum_stripped and not enum_stripped.startswith('//'):
                    extracted.append(enum_line)
                
                #check for closing brace (simple enum with no body)
                if enum_stripped == '}':
                    break
                
                j += 1
            continue
        
        #sealed class/interface - capture with subclasses
        if patterns['sealed_class'].match(stripped):
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            
            extracted.append(line)
            processed_lines.add(i)
            
            #find body and extract subclasses
            j = i + 1
            sealed_brace_depth = open_braces - close_braces
            
            #find opening brace if not on same line
            while j < len(lines) and sealed_brace_depth == 0:
                sealed_line = lines[j].strip()
                if '{' in sealed_line:
                    sealed_brace_depth = 1
                    processed_lines.add(j)
                j += 1
            
            #extract nested classes/objects (subclasses)
            while j < len(lines) and sealed_brace_depth > 0:
                sealed_line = lines[j]
                sealed_stripped = sealed_line.strip()
                
                sealed_brace_depth += sealed_stripped.count('{') - sealed_stripped.count('}')
                
                #capture nested class/object/data class declarations
                if patterns['class'].match(sealed_stripped):
                    extracted.append(sealed_line)
                    processed_lines.add(j)
                
                j += 1
            continue
        
        #companion object - capture with body
        if patterns['companion'].match(stripped):
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            
            extracted.append(line)
            processed_lines.add(i)
            
            #find and extract companion body
            j = i + 1
            companion_brace_depth = open_braces - close_braces
            
            #find opening brace if not on same line
            while j < len(lines) and companion_brace_depth == 0:
                comp_line = lines[j].strip()
                if '{' in comp_line:
                    companion_brace_depth = 1
                    processed_lines.add(j)
                j += 1
            
            #extract companion content
            while j < len(lines) and companion_brace_depth > 0:
                comp_line = lines[j]
                comp_stripped = comp_line.strip()
                
                companion_brace_depth += comp_stripped.count('{') - comp_stripped.count('}')
                processed_lines.add(j)
                
                #capture const vals
                if 'const val' in comp_stripped:
                    extracted.append(comp_line)
                #capture functions (just signature for now)
                elif patterns['function'].match(comp_stripped):
                    extracted.append(comp_line)
                #capture properties
                elif patterns['property'].match(comp_stripped) and companion_brace_depth == 1:
                    extracted.append(comp_line)
                #closing brace
                elif comp_stripped == '}' and companion_brace_depth == 0:
                    extracted.append(comp_line)
                
                j += 1
            continue
        
        #regular class/object declaration
        match = patterns['class'].match(stripped)
        if match:
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            extracted.append(line)
            continue
        
        #interface declaration
        match = patterns['interface'].match(stripped)
        if match:
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            extracted.append(line)
            continue
        
        #function declaration - capture signature + body preview
        if patterns['function'].match(stripped):
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            
            func_lines = [line]
            processed_lines.add(i)
            j = i
            
            #handle multi-line signature
            if '(' in stripped and ')' not in stripped:
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    func_lines.append(lines[j])
                    processed_lines.add(j)
                    j += 1
                if j < len(lines):
                    func_lines.append(lines[j])
                    processed_lines.add(j)
                    j += 1
            else:
                j = i + 1
            
            #check if this is an abstract/interface method (no body)
            full_sig = '\n'.join(func_lines)
            has_body = '{' in full_sig
            
            #look ahead for opening brace if not in signature
            if not has_body and j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith('{'):
                    has_body = True
                elif next_line == '' or next_line.startswith('//'):
                    #skip empty/comment lines and check next
                    k = j + 1
                    while k < len(lines) and (lines[k].strip() == '' or lines[k].strip().startswith('//')):
                        k += 1
                    if k < len(lines) and lines[k].strip().startswith('{'):
                        has_body = True
            
            #if no body (interface/abstract method), just output signature
            if not has_body:
                extracted.append(full_sig)
                continue
            
            #find function body boundaries
            func_brace_depth = 0
            func_started = False
            body_lines = []
            return_lines = []
            
            #check if signature line has opening brace
            for fl in func_lines:
                if '{' in fl:
                    func_started = True
                    func_brace_depth += fl.count('{') - fl.count('}')
            
            #collect body lines
            while j < len(lines):
                body_line = lines[j]
                body_stripped = body_line.strip()
                
                if '{' in body_stripped:
                    func_started = True
                
                if func_started:
                    func_brace_depth += body_stripped.count('{') - body_stripped.count('}')
                    processed_lines.add(j)
                    
                    #collect non-empty, non-comment lines
                    if body_stripped and not body_stripped.startswith('//'):
                        body_lines.append(body_line)
                        #track return statements
                        if body_stripped.startswith('return ') or body_stripped == 'return':
                            return_lines.append(body_line)
                    
                    #function ended
                    if func_brace_depth <= 0:
                        break
                
                j += 1
            
            #build function output: signature + first N body lines + last few lines
            max_body_lines = 8
            last_lines_count = 3
            output_lines = func_lines.copy()
            
            if body_lines:
                total_body = len(body_lines)
                
                #get first N lines
                first_lines = []
                returns_in_first = set()
                for bl in body_lines[:max_body_lines]:
                    first_lines.append(bl)
                    if bl.strip().startswith('return'):
                        returns_in_first.add(bl.strip())
                
                output_lines.extend(first_lines)
                
                #check if we need truncation
                remaining = total_body - max_body_lines
                if remaining > last_lines_count:
                    #add truncation marker
                    indent = '        '
                    output_lines.append(f'{indent}// ... ({remaining - last_lines_count} more lines)')
                    
                    #add last 2-3 lines (excluding closing brace if it's the last)
                    last_lines = body_lines[-(last_lines_count + 1):-1] if body_lines[-1].strip() == '}' else body_lines[-last_lines_count:]
                    for ll in last_lines:
                        if ll.strip() and ll not in first_lines:
                            output_lines.append(ll)
                    
                    #add closing brace
                    if body_lines[-1].strip() == '}':
                        output_lines.append(body_lines[-1])
                    else:
                        output_lines.append('    }')
                elif remaining > 0:
                    #just add the remaining lines (not enough to truncate)
                    for bl in body_lines[max_body_lines:]:
                        output_lines.append(bl)
            
            extracted.append('\n'.join(output_lines))
            continue
        
        #constructor
        if patterns['constructor'].match(stripped):
            #flush pending annotations
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            
            full_sig = line
            if '(' in stripped and ')' not in stripped:
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    full_sig += '\n' + lines[j]
                    processed_lines.add(j)
                    j += 1
                if j < len(lines):
                    full_sig += '\n' + lines[j]
                    processed_lines.add(j)
            extracted.append(full_sig)
            continue
        
        #init block - start capturing
        if patterns['init'].match(stripped):
            in_init_block = True
            init_brace_depth = open_braces - close_braces
            init_content = []
            continue
        
        #property declaration (class-level only, when brace_depth <= 2)
        if brace_depth <= 2 and patterns['property'].match(stripped):
            #flush pending annotations (like @Inject)
            if pending_annotations:
                extracted.extend(pending_annotations)
                pending_annotations = []
            
            #keep the full line for property declarations
            if len(line) > 100:
                #truncate very long lines but keep the important parts
                if '=' in line:
                    parts = line.split('=', 1)
                    rhs = parts[1].strip()
                    if len(rhs) > 50:
                        extracted.append(f'{parts[0]}= {rhs[:45]}...')
                    else:
                        extracted.append(line)
                else:
                    extracted.append(line)
            else:
                extracted.append(line)
            continue
        
        #typealias
        if patterns['typealias'].match(stripped):
            extracted.append(line)
            continue
    
    #condense imports at the top
    result = []
    if imports:
        #group imports by top-level package
        import_groups = {}
        for imp in imports:
            parts = imp.replace('import ', '').split('.')
            if len(parts) >= 2:
                key = f"{parts[0]}.{parts[1]}"
            else:
                key = parts[0]
            if key not in import_groups:
                import_groups[key] = []
            import_groups[key].append(imp)
        
        #output condensed imports
        result.append('//imports:')
        for group_key in sorted(import_groups.keys()):
            if len(import_groups[group_key]) > 3:
                result.append(f'//  {group_key}.* ({len(import_groups[group_key])} imports)')
            else:
                for imp in import_groups[group_key]:
                    result.append(f'//  {imp.replace("import ", "")}')
        result.append('')
    
    result.extend(extracted)
    return '\n'.join(result)


def compress_typescript(content):
    """
    Extract structural elements from TypeScript/JavaScript code:
    - Import/export statements
    - Interface/type definitions
    - Class declarations
    - Function signatures
    - Return statements
    """
    lines = content.split('\n')
    extracted = []
    in_multiline_comment = False
    
    patterns = {
        'import': re.compile(r'^\s*import\s+'),
        'export': re.compile(r'^\s*export\s+'),
        'interface': re.compile(r'^\s*(?:export\s+)?interface\s+(\w+)'),
        'type': re.compile(r'^\s*(?:export\s+)?type\s+(\w+)'),
        'class': re.compile(r'^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)'),
        'function': re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)'),
        'arrow_func': re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>'),
        'method': re.compile(r'^\s*(?:public\s+|private\s+|protected\s+|static\s+|async\s+|readonly\s+)*(\w+)\s*\([^)]*\)\s*(?::\s*\S+)?\s*\{'),
        'return': re.compile(r'^\s*return\s+'),
    }
    
    imports = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        #handle multi-line comments
        if '/*' in stripped and '*/' not in stripped:
            in_multiline_comment = True
            continue
        if '*/' in stripped:
            in_multiline_comment = False
            continue
        if in_multiline_comment:
            continue
        
        if stripped.startswith('//') or not stripped:
            continue
        
        #imports
        if patterns['import'].match(stripped):
            imports.append(stripped)
            continue
        
        #exports (type/interface/class exports)
        if patterns['interface'].match(stripped):
            extracted.append(line)
            continue
        
        if patterns['type'].match(stripped):
            extracted.append(line)
            continue
        
        if patterns['class'].match(stripped):
            extracted.append(line)
            continue
        
        if patterns['function'].match(stripped):
            extracted.append(line)
            continue
        
        if patterns['arrow_func'].match(stripped):
            extracted.append(line)
            continue
        
        if patterns['method'].match(stripped):
            extracted.append(line)
            continue
        
        if patterns['return'].match(stripped):
            if len(stripped) > 80:
                extracted.append(f'{line[:len(line)-len(stripped)]}return ...')
            else:
                extracted.append(line)
            continue
    
    #condense imports
    result = []
    if imports:
        result.append('//imports:')
        for imp in imports[:10]:
            result.append(f'//  {imp[:80]}...' if len(imp) > 80 else f'//  {imp}')
        if len(imports) > 10:
            result.append(f'//  ...and {len(imports) - 10} more imports')
        result.append('')
    
    result.extend(extracted)
    return '\n'.join(result)


def compress_python(content):
    """
    Extract structural elements from Python code:
    - Import statements
    - Class definitions
    - Function/method definitions
    - Return statements
    """
    lines = content.split('\n')
    extracted = []
    
    patterns = {
        'import': re.compile(r'^\s*(?:import|from)\s+'),
        'class': re.compile(r'^\s*class\s+(\w+)'),
        'function': re.compile(r'^\s*(?:async\s+)?def\s+(\w+)\s*\('),
        'return': re.compile(r'^\s*return\s+'),
        'decorator': re.compile(r'^\s*@\w+'),
    }
    
    imports = []
    pending_decorators = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if stripped.startswith('#') or not stripped:
            continue
        
        #imports
        if patterns['import'].match(stripped):
            imports.append(stripped)
            continue
        
        #decorators (collect to attach to next function/class)
        if patterns['decorator'].match(stripped):
            pending_decorators.append(line)
            continue
        
        #class definition
        if patterns['class'].match(stripped):
            if pending_decorators:
                extracted.extend(pending_decorators)
                pending_decorators = []
            extracted.append(line)
            continue
        
        #function definition
        if patterns['function'].match(stripped):
            if pending_decorators:
                extracted.extend(pending_decorators)
                pending_decorators = []
            #capture full signature if multi-line
            full_sig = line
            if '(' in stripped and ')' not in stripped:
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    full_sig += '\n' + lines[j]
                    j += 1
                if j < len(lines):
                    full_sig += '\n' + lines[j]
            extracted.append(full_sig)
            continue
        
        #clear pending decorators if we hit something else
        pending_decorators = []
        
        #return statements
        if patterns['return'].match(stripped):
            if len(stripped) > 80:
                extracted.append(f'{line[:len(line)-len(stripped)]}return ...')
            else:
                extracted.append(line)
            continue
    
    #condense imports
    result = []
    if imports:
        result.append('#imports:')
        for imp in imports[:15]:
            result.append(f'#  {imp}')
        if len(imports) > 15:
            result.append(f'#  ...and {len(imports) - 15} more imports')
        result.append('')
    
    result.extend(extracted)
    return '\n'.join(result)


def compress_aidl(content):
    """
    Extract structural elements from AIDL files:
    - Package declaration
    - Import statements
    - Interface definitions
    - Method signatures
    """
    lines = content.split('\n')
    extracted = []
    
    patterns = {
        'package': re.compile(r'^\s*package\s+[\w.]+;'),
        'import': re.compile(r'^\s*import\s+[\w.]+;'),
        'interface': re.compile(r'^\s*(?:oneway\s+)?interface\s+(\w+)'),
        'parcelable': re.compile(r'^\s*parcelable\s+(\w+)'),
        'method': re.compile(r'^\s*(?:oneway\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\('),
    }
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('//') or stripped.startswith('/*') or not stripped:
            continue
        
        for pattern_name, pattern in patterns.items():
            if pattern.match(stripped):
                extracted.append(line)
                break
    
    return '\n'.join(extracted)


def compress_groovy(content):
    """
    Extract structural elements from Groovy/Gradle files:
    - Plugin applications
    - Dependencies block entries
    - Task definitions
    - Function definitions
    """
    lines = content.split('\n')
    extracted = []
    in_dependencies = False
    brace_depth = 0
    
    patterns = {
        'plugins': re.compile(r'^\s*(?:id|alias)\s*[\'"\(]'),
        'apply': re.compile(r'^\s*apply\s+'),
        'dependencies_start': re.compile(r'^\s*dependencies\s*\{'),
        'dependency': re.compile(r'^\s*(?:implementation|api|compileOnly|runtimeOnly|testImplementation|androidTestImplementation|kapt|ksp|annotationProcessor)\s*[\(\']'),
        'task': re.compile(r'^\s*(?:task|tasks\.register)\s*[\(\']?(\w+)'),
        'function': re.compile(r'^\s*(?:def|void|String|int|boolean)\s+(\w+)\s*\('),
        'android_block': re.compile(r'^\s*android\s*\{'),
        'buildTypes': re.compile(r'^\s*(?:debug|release|buildTypes)\s*\{?'),
    }
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('//') or not stripped:
            continue
        
        brace_depth += stripped.count('{') - stripped.count('}')
        
        #track dependencies block
        if patterns['dependencies_start'].match(stripped):
            in_dependencies = True
            extracted.append(line)
            continue
        
        if in_dependencies:
            if brace_depth == 0:
                in_dependencies = False
                extracted.append('}')
            elif patterns['dependency'].match(stripped):
                extracted.append(line)
            continue
        
        #plugins
        if patterns['plugins'].match(stripped):
            extracted.append(line)
            continue
        
        #apply statements
        if patterns['apply'].match(stripped):
            extracted.append(line)
            continue
        
        #task definitions
        if patterns['task'].match(stripped):
            extracted.append(line)
            continue
        
        #function definitions
        if patterns['function'].match(stripped):
            extracted.append(line)
            continue
        
        #android block header
        if patterns['android_block'].match(stripped):
            extracted.append(line)
            continue
        
        #build types
        if patterns['buildTypes'].match(stripped):
            extracted.append(line)
            continue
    
    return '\n'.join(extracted)


def compress_graphql(content):
    """
    Light compression for GraphQL files (Apollo Kotlin).
    Strips comments and normalizes whitespace while preserving all structure.
    
    Removes:
    - Single-line comments (#)
    - Multi-line docstrings (triple quotes)
    - Excessive blank lines
    - Trailing whitespace
    
    Preserves:
    - All type definitions with full field details
    - All query/mutation/subscription operations with full selection sets
    - All fragments with full field selections
    - Directives and their arguments
    - Variable definitions
    """
    lines = content.split('\n')
    result = []
    in_docstring = False
    prev_blank = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        #handle multi-line docstrings (""")
        if in_docstring:
            if '"""' in stripped:
                in_docstring = False
            i += 1
            continue
        
        #check for docstring start
        if stripped.startswith('"""'):
            if stripped.count('"""') >= 2:
                #single-line docstring, skip it
                i += 1
                continue
            else:
                #multi-line docstring starts
                in_docstring = True
                i += 1
                continue
        
        #skip single-line comments
        if stripped.startswith('#'):
            i += 1
            continue
        
        #handle inline comments (remove comment portion)
        if '#' in stripped:
            #check if # is inside a string (basic check)
            quote_count = stripped.count('"')
            hash_pos = stripped.find('#')
            #simple heuristic: if even number of quotes before #, it's a comment
            before_hash = stripped[:hash_pos]
            if before_hash.count('"') % 2 == 0:
                stripped = stripped[:hash_pos].rstrip()
                if not stripped:
                    i += 1
                    continue
        
        #skip empty lines but allow one blank line between blocks
        if not stripped:
            if not prev_blank and result:
                result.append('')
                prev_blank = True
            i += 1
            continue
        
        prev_blank = False
        
        #preserve the line with original indentation
        #but normalize excessive internal whitespace for long lines
        if len(line) > 120:
            #normalize whitespace in very long lines
            normalized = re.sub(r'[ \t]+', ' ', line)
            result.append(normalized.rstrip())
        else:
            result.append(line.rstrip())
        
        i += 1
    
    #remove trailing blank lines
    while result and not result[-1]:
        result.pop()
    
    #remove leading blank lines
    while result and not result[0]:
        result.pop(0)
    
    return '\n'.join(result)


def compress_content(content, language):
    """
    Compress content based on language.
    Returns compressed content or original if language not supported.
    """
    compressors = {
        'kotlin': compress_kotlin,
        'gradle-kotlin': compress_kotlin,
        'typescript': compress_typescript,
        'javascript': compress_typescript,
        'tsx': compress_typescript,
        'jsx': compress_typescript,
        'python': compress_python,
        'aidl': compress_aidl,
        'gradle': compress_groovy,
        'groovy': compress_groovy,
        'graphql': compress_graphql,
    }
    
    compressor = compressors.get(language)
    if compressor:
        compressed = compressor(content)
        return compressed if compressed.strip() else content
    
    #for unsupported languages, return original
    return content


def get_compression_stats(original, compressed):
    """Calculate compression statistics."""
    original_lines = len(original.split('\n'))
    compressed_lines = len(compressed.split('\n'))
    original_chars = len(original)
    compressed_chars = len(compressed)
    
    return {
        'original_lines': original_lines,
        'compressed_lines': compressed_lines,
        'original_chars': original_chars,
        'compressed_chars': compressed_chars,
        'line_reduction': round((1 - compressed_lines / max(original_lines, 1)) * 100, 1),
        'char_reduction': round((1 - compressed_chars / max(original_chars, 1)) * 100, 1),
    }


#=============================================================================
#core functions
#=============================================================================

def estimate_tokens(text):
    """
    Estimate token count (rough approximation: 1 token ≈ 4 characters).
    Conservative estimate to be safe.
    """
    return len(text) // 3  #conservative estimate


def count_lines(file_path):
    """Count lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def get_file_content(file_path):
    """Read file content safely."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"<!-- Error reading file: {str(e)} -->"


def create_code_snippet(file_path, counter, recursive, base_path, compress=False):
    """Create XML code snippet for a single file."""
    filename = file_path.name
    
    #get relative path for recursive mode
    if recursive:
        try:
            relative_path = file_path.relative_to(base_path)
            relative_path = str(relative_path).replace('\\', '/')
        except ValueError:
            relative_path = filename
    else:
        relative_path = filename
    
    #detect language
    language = detect_language(filename)
    
    #get file info
    extension = file_path.suffix.lstrip('.')
    line_count = count_lines(file_path)
    size_bytes = file_path.stat().st_size
    
    #read file content
    original_content = get_file_content(file_path)
    
    #apply compression if enabled
    if compress:
        content = compress_content(original_content, language)
        stats = get_compression_stats(original_content, content)
        compression_attr = f' compressed="true" reduction="{stats["line_reduction"]}%"'
    else:
        content = original_content
        compression_attr = ''
    
    #build XML block
    xml_parts = [f'  <code{counter}']
    xml_parts.append(f'    file="{filename}"')
    if recursive:
        xml_parts.append(f'    path="{relative_path}"')
    xml_parts.append(f'    language="{language}"')
    xml_parts.append(f'    extension="{extension}"')
    xml_parts.append(f'    lines="{line_count}"')
    xml_parts.append(f'    size_bytes="{size_bytes}"{compression_attr}>')
    xml_parts.append('    <![CDATA[')
    xml_parts.append(content)
    xml_parts.append('    ]]>')
    xml_parts.append(f'  </code{counter}>')
    
    return '\n'.join(xml_parts)


def create_metadata(folder_path, file_count, start_num, recursive, compress=False, chunk_num=None, total_chunks=None, include_tree=False):
    """Create metadata section."""
    timestamp = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    lines = [
        '  <metadata>',
        f'    <source_folder>{folder_path}</source_folder>',
        f'    <generated_at>{timestamp}</generated_at>',
        f'    <file_count>{file_count}</file_count>',
        f'    <starting_number>{start_num}</starting_number>',
        f'    <recursive>{str(recursive).lower()}</recursive>',
        f'    <compress_mode>{str(compress).lower()}</compress_mode>',
        f'    <includes_tree>{str(include_tree).lower()}</includes_tree>',
    ]
    
    if compress:
        lines.append('    <compress_info>Extracts: classes, functions, interfaces, returns</compress_info>')
    
    if chunk_num is not None and total_chunks is not None:
        lines.append(f'    <chunk>{chunk_num}/{total_chunks}</chunk>')
    
    lines.append('  </metadata>')
    return '\n'.join(lines)


def write_chunk(output_file, root_tag, content_lines, folder_path, file_count, start_num, recursive, compress=False, chunk_num=None, total_chunks=None, tree_section=None):
    """Write a single chunk file."""
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<{root_tag}>',
        create_metadata(folder_path, file_count, start_num, recursive, compress, chunk_num, total_chunks, include_tree=(tree_section is not None)),
    ]
    
    #add project structure tree if provided (only in first chunk)
    if tree_section:
        xml_lines.append(tree_section)
    
    xml_lines.extend(content_lines)
    xml_lines.append(f'</{root_tag}>')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(xml_lines))


def main():
    """Main function with chunking support."""
    
    parser = argparse.ArgumentParser(
        description='Copy code files with automatic chunking for AI token limits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s /path/to/project --filter-ext kt
  %(prog)s /path/to/project --compress --filter-ext kt kts
  %(prog)s . --compress --max-tokens 30000
  %(prog)s /path/to/project --include-tree --filter-ext kt java xml
  %(prog)s /path/to/project --compress --filter-ext kt graphql graphqls

Compress mode extracts only structural elements:
  - Class/object/interface declarations
  - Function/method signatures
  - Property declarations (Kotlin)
  - Return statements
  - Import statements (condensed)

Directory tree mode (--include-tree):
  - Adds ASCII project structure to output
  - Helps AI understand project organization
  - Only included in first chunk (multi-chunk outputs)

Supported languages for compression:
  - Kotlin (.kt, .kts)
  - TypeScript/JavaScript (.ts, .tsx, .js, .jsx)
  - Python (.py)
  - AIDL (.aidl)
  - Gradle/Groovy (.gradle, .groovy)
  - GraphQL (.graphql, .graphqls) - Apollo Kotlin support
    * Light compression: strips comments/docstrings, preserves all fields
'''
    )
    parser.add_argument(
        'folder_path',
        nargs='?',
        default='.',
        help='Path to folder containing code files (default: current directory)'
    )
    parser.add_argument(
        '--root-tag',
        default='code_snippets',
        help='Name for root XML tag (default: code_snippets)'
    )
    parser.add_argument(
        '--start-num',
        type=int,
        default=1,
        help='Starting number for code tags (default: 1)'
    )
    parser.add_argument(
        '--recursive',
        type=lambda x: x.lower() in ('true', '1', 'yes'),
        default=True,
        help='Recursive folder scan: true/false (default: true)'
    )
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=45000,
        help='Maximum tokens per file (default: 45000 for 50K limit with safety margin)'
    )
    parser.add_argument(
        '--filter-ext',
        nargs='+',
        help='Filter by extensions (e.g., --filter-ext kt java xml)'
    )
    parser.add_argument(
        '--exclude-ext',
        nargs='+',
        help='Exclude extensions (e.g., --exclude-ext json xml)'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process'
    )
    parser.add_argument(
        '--compress',
        action='store_true',
        help='Enable compress mode: extract only classes, functions, interfaces, and returns'
    )
    parser.add_argument(
        '--include-tree',
        action='store_true',
        help='Include AI-friendly directory structure tree in output'
    )
    parser.add_argument(
        '--tree-depth',
        type=int,
        default=None,
        help='Maximum depth for directory tree (default: unlimited)'
    )
    parser.add_argument(
        '--output-prefix',
        default='codesnippet',
        help='Prefix for output files (default: codesnippet)'
    )
    
    args = parser.parse_args()
    
    #validate inputs
    folder_path = Path(args.folder_path)
    
    if not folder_path.exists():
        print(f"Error: Folder '{args.folder_path}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not folder_path.is_dir():
        print(f"Error: '{args.folder_path}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    #validate max_tokens is reasonable
    min_tokens = 1000
    if args.max_tokens < min_tokens:
        print(f"Error: --max-tokens must be at least {min_tokens}", file=sys.stderr)
        sys.exit(1)
    
    #get list of files
    if args.recursive:
        files = sorted(folder_path.rglob('*'))
        files = [f for f in files if f.is_file()]
    else:
        files = sorted(folder_path.glob('*'))
        files = [f for f in files if f.is_file()]
    
    #apply filters
    if args.filter_ext:
        filter_exts = [e.lstrip('.').lower() for e in args.filter_ext]
        files = [f for f in files if f.suffix.lstrip('.').lower() in filter_exts]
    
    if args.exclude_ext:
        exclude_exts = [e.lstrip('.').lower() for e in args.exclude_ext]
        files = [f for f in files if f.suffix.lstrip('.').lower() not in exclude_exts]
    
    if args.max_files:
        files = files[:args.max_files]
    
    #check if any files found
    if not files:
        print(f"Warning: No files found matching criteria")
        sys.exit(0)
    
    mode_str = "COMPRESS" if args.compress else "FULL"
    print(f"Found {len(files)} files to process (Mode: {mode_str})")
    
    if args.compress:
        print("Compress mode: extracting classes, functions, interfaces, returns")
    
    #generate directory tree if requested
    tree_section = None
    tree_tokens = 0
    if args.include_tree:
        tree_content = generate_directory_tree(files, folder_path, args.tree_depth)
        total_dirs = count_directories(files, folder_path)
        tree_section = create_project_structure_section(tree_content, len(files), total_dirs)
        tree_tokens = estimate_tokens(tree_section)
        print(f"Directory tree: {total_dirs} directories (~{tree_tokens:,} tokens)")
    
    #process files and split into chunks
    chunks = []
    current_chunk = []
    current_tokens = 0
    counter = args.start_num
    chunk_file_count = 0
    large_standalone_files = []
    total_reduction = []
    
    #estimate overhead for XML structure (increased if tree is included in first chunk)
    base_overhead_tokens = 500
    first_chunk_overhead = base_overhead_tokens + tree_tokens if args.include_tree else base_overhead_tokens
    
    for file_path in files:
        snippet = create_code_snippet(file_path, counter, args.recursive, folder_path, args.compress)
        snippet_tokens = estimate_tokens(snippet)
        
        #track compression stats
        if args.compress:
            original_content = get_file_content(file_path)
            original_tokens = estimate_tokens(original_content)
            if original_tokens > 0:
                reduction = (1 - snippet_tokens / original_tokens) * 100
                total_reduction.append(reduction)
        
        #determine overhead for current chunk (first chunk may include tree)
        is_first_chunk = len(chunks) == 0
        current_overhead = first_chunk_overhead if is_first_chunk and not current_chunk else base_overhead_tokens
        
        #check if this single file exceeds the limit
        if snippet_tokens + current_overhead > args.max_tokens:
            #file is too large for any chunk - put it in its own chunk
            if current_chunk:
                #save current chunk first
                chunks.append({
                    'content': current_chunk,
                    'start_num': counter - chunk_file_count,
                    'file_count': chunk_file_count
                })
                current_chunk = []
                current_tokens = 0
                chunk_file_count = 0
            
            #add this large file as its own chunk
            chunks.append({
                'content': [snippet],
                'start_num': counter,
                'file_count': 1
            })
            
            large_standalone_files.append({
                'path': file_path,
                'tokens': snippet_tokens,
                'code_num': counter
            })
            
            counter += 1
            continue
        
        #check if adding this file would exceed limit
        if current_tokens + snippet_tokens + current_overhead > args.max_tokens and current_chunk:
            #save current chunk and start new one
            chunks.append({
                'content': current_chunk,
                'start_num': counter - chunk_file_count,
                'file_count': chunk_file_count
            })
            current_chunk = []
            current_tokens = 0
            chunk_file_count = 0
        
        #add file to current chunk
        current_chunk.append(snippet)
        current_tokens += snippet_tokens
        chunk_file_count += 1
        counter += 1
    
    #add last chunk
    if current_chunk:
        chunks.append({
            'content': current_chunk,
            'start_num': counter - chunk_file_count,
            'file_count': chunk_file_count
        })
    
    #write chunks to files
    total_chunks = len(chunks)
    compress_suffix = '_compressed' if args.compress else ''
    
    if total_chunks == 1:
        #single file
        output_file = f'{args.output_prefix}{compress_suffix}.text'
        write_chunk(
            output_file,
            args.root_tag,
            chunks[0]['content'],
            args.folder_path,
            chunks[0]['file_count'],
            args.start_num,
            args.recursive,
            args.compress,
            tree_section=tree_section  #include tree in single file
        )
        print(f"\n✅ Created {output_file}")
        print(f"   Files: {chunks[0]['file_count']}")
        if args.include_tree:
            print(f"   Includes: directory tree")
        print(f"   Estimated tokens: ~{estimate_tokens(open(output_file).read()):,}")
    else:
        #multiple chunks
        for i, chunk in enumerate(chunks, 1):
            output_file = f'{args.output_prefix}{compress_suffix}_part{i}_of_{total_chunks}.text'
            #only include tree in first chunk
            chunk_tree = tree_section if i == 1 else None
            write_chunk(
                output_file,
                args.root_tag,
                chunk['content'],
                args.folder_path,
                chunk['file_count'],
                chunk['start_num'],
                args.recursive,
                args.compress,
                i,
                total_chunks,
                tree_section=chunk_tree
            )
            tokens = estimate_tokens(open(output_file).read())
            print(f"\n✅ Created {output_file}")
            print(f"   Files: {chunk['file_count']}")
            print(f"   Code tags: <code{chunk['start_num']}> to <code{chunk['start_num'] + chunk['file_count'] - 1}>")
            if i == 1 and args.include_tree:
                print(f"   Includes: directory tree")
            print(f"   Estimated tokens: ~{tokens:,}")
    
    print(f"\n📊 Summary:")
    print(f"   Total files processed: {len(files)}")
    print(f"   Total chunks created: {total_chunks}")
    print(f"   Recursive mode: {args.recursive}")
    print(f"   Compress mode: {args.compress}")
    print(f"   Directory tree: {args.include_tree}")
    
    if args.compress and total_reduction:
        avg_reduction = sum(total_reduction) / len(total_reduction)
        print(f"   Average token reduction: ~{avg_reduction:.1f}%")
    
    if large_standalone_files:
        print(f"\n⚠️  Large files in dedicated chunks (exceed {args.max_tokens:,} tokens):")
        for lf in large_standalone_files[:10]:  #show first 10
            print(f"   - {lf['path'].name} (~{lf['tokens']:,} tokens) → code{lf['code_num']} (dedicated chunk)")
        if len(large_standalone_files) > 10:
            print(f"   ... and {len(large_standalone_files) - 10} more")
        print(f"\n   Note: These files are complete but in their own chunks")
    
    if total_chunks > 1:
        print(f"\n💡 Tip: Upload files to AI in order (part1, part2, etc.)")
        if args.include_tree:
            print(f"   Directory tree is only in part1 for context efficiency")


if __name__ == '__main__':
    main()
