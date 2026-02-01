#!/usr/bin/env python3
"""
Script to copy code files with automatic chunking for AI token limits.
Usage: python copy_code_snippets_chunked.py [folder_path] [options]

Compress mode extracts only structural elements:
- Class names and declarations
- Function/method definitions (signatures)
- Interface definitions
- Return statements
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime
import argparse


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
#compress mode functions - extract structural elements only
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


def create_metadata(folder_path, file_count, start_num, recursive, compress=False, chunk_num=None, total_chunks=None):
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
    ]
    
    if compress:
        lines.append('    <compress_info>Extracts: classes, functions, interfaces, returns</compress_info>')
    
    if chunk_num is not None and total_chunks is not None:
        lines.append(f'    <chunk>{chunk_num}/{total_chunks}</chunk>')
    
    lines.append('  </metadata>')
    return '\n'.join(lines)


def write_chunk(output_file, root_tag, content_lines, folder_path, file_count, start_num, recursive, compress=False, chunk_num=None, total_chunks=None):
    """Write a single chunk file."""
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<{root_tag}>',
        create_metadata(folder_path, file_count, start_num, recursive, compress, chunk_num, total_chunks),
    ]
    
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

Compress mode extracts only structural elements:
  - Class/object/interface declarations
  - Function/method signatures
  - Property declarations (Kotlin)
  - Return statements
  - Import statements (condensed)

Supported languages for compression:
  - Kotlin (.kt, .kts)
  - TypeScript/JavaScript (.ts, .tsx, .js, .jsx)
  - Python (.py)
  - AIDL (.aidl)
  - Gradle/Groovy (.gradle, .groovy)
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
    
    #process files and split into chunks
    chunks = []
    current_chunk = []
    current_tokens = 0
    counter = args.start_num
    chunk_file_count = 0
    large_standalone_files = []
    total_reduction = []
    
    #estimate overhead for XML structure
    overhead_tokens = 500
    
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
        
        #check if this single file exceeds the limit
        if snippet_tokens + overhead_tokens > args.max_tokens:
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
        if current_tokens + snippet_tokens + overhead_tokens > args.max_tokens and current_chunk:
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
            args.compress
        )
        print(f"\n✅ Created {output_file}")
        print(f"   Files: {chunks[0]['file_count']}")
        print(f"   Estimated tokens: ~{estimate_tokens(open(output_file).read()):,}")
    else:
        #multiple chunks
        for i, chunk in enumerate(chunks, 1):
            output_file = f'{args.output_prefix}{compress_suffix}_part{i}_of_{total_chunks}.text'
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
                total_chunks
            )
            tokens = estimate_tokens(open(output_file).read())
            print(f"\n✅ Created {output_file}")
            print(f"   Files: {chunk['file_count']}")
            print(f"   Code tags: <code{chunk['start_num']}> to <code{chunk['start_num'] + chunk['file_count'] - 1}>")
            print(f"   Estimated tokens: ~{tokens:,}")
    
    print(f"\n📊 Summary:")
    print(f"   Total files processed: {len(files)}")
    print(f"   Total chunks created: {total_chunks}")
    print(f"   Recursive mode: {args.recursive}")
    print(f"   Compress mode: {args.compress}")
    
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


if __name__ == '__main__':
    main()
