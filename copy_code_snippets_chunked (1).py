#!/usr/bin/env python3
"""
Script to copy code files with automatic chunking for AI token limits.
Usage: python copy_code_snippets_chunked.py [folder_path] [options]

Compress mode extracts only structural elements:
- Class names and declarations
- Function/method definitions (signatures)
- Interface definitions
- Return statements

GraphQL support (Apollo Kotlin):
- Light compression: strips comments/docstrings, preserves all fields

Directory tree mode includes project structure for AI context.

Git integration:
- Include uncommitted changes (diffs)
- Include commit history (logs)
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
from collections import defaultdict


#=============================================================================
#constants - build folders and image extensions
#=============================================================================

#folders to always exclude (case-insensitive matching)
BUILD_FOLDERS = {
    'build', 'out', 'bin', '.gradle', '.idea', 'node_modules',
    '__pycache__', '.git', 'target', 'dist', '.cache', '.venv',
    'venv', 'env', '.env', '.tox', '.mypy_cache', '.pytest_cache',
    'coverage', '.coverage', 'htmlcov', '.eggs', '*.egg-info',
    '.bundle', 'vendor', 'Pods', 'DerivedData', '.build',
    'intermediates', 'generated', 'tmp', 'temp', '.temp'
}

#image file extensions
IMAGE_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp',
    'tiff', 'tif', 'heic', 'heif', 'raw', 'psd', 'ai', 'eps'
}


def is_build_folder(path):
    """
    Check if any part of the path is a build/generated folder.
    
    Args:
        path: Path object or string
    
    Returns:
        bool: True if path contains a build folder
    """
    path_str = str(path).replace('\\', '/')
    parts = path_str.lower().split('/')
    
    for part in parts:
        if part in BUILD_FOLDERS:
            return True
        #check for patterns like *.egg-info
        if part.endswith('.egg-info'):
            return True
    
    return False


def is_image_file(filename):
    """
    Check if file is an image based on extension.
    
    Args:
        filename: File name or path
    
    Returns:
        bool: True if file is an image
    """
    ext = Path(filename).suffix.lstrip('.').lower()
    return ext in IMAGE_EXTENSIONS


def get_image_type(filename):
    """
    Get human-readable image type from extension.
    
    Args:
        filename: File name or path
    
    Returns:
        str: Image type description
    """
    ext = Path(filename).suffix.lstrip('.').lower()
    type_map = {
        'png': 'PNG',
        'jpg': 'JPEG',
        'jpeg': 'JPEG',
        'gif': 'GIF',
        'webp': 'WebP',
        'svg': 'SVG',
        'ico': 'Icon',
        'bmp': 'Bitmap',
        'tiff': 'TIFF',
        'tif': 'TIFF',
        'heic': 'HEIC',
        'heif': 'HEIF',
        'raw': 'RAW',
        'psd': 'Photoshop',
        'ai': 'Illustrator',
        'eps': 'EPS'
    }
    return type_map.get(ext, ext.upper())


#=============================================================================
#constants - exclusions and file types
#=============================================================================

#build folders to always exclude
BUILD_FOLDER_PATTERNS = {
    'build', 'out', '.gradle', '.idea', 'node_modules',
    '__pycache__', '.pytest_cache', 'dist', 'target',
    '.git', '.svn', '.hg', 'bin', 'obj', '.vs',
    'generated', 'intermediates', 'tmp', 'temp',
    '.dart_tool', '.pub-cache', 'Pods', '.expo',
}

#image extensions (content not included, only metadata)
IMAGE_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
    'ico', 'bmp', 'tiff', 'tif', 'heic', 'heif',
    'raw', 'psd', 'ai', 'eps',
}


def is_build_folder(path):
    """Check if any part of the path is a build folder."""
    parts = Path(path).parts
    for part in parts:
        if part.lower() in BUILD_FOLDER_PATTERNS:
            return True
        #check for .egg-info pattern
        if part.lower().endswith('.egg-info'):
            return True
    return False


def is_image_file(filename):
    """Check if file is an image based on extension."""
    ext = Path(filename).suffix.lstrip('.').lower()
    return ext in IMAGE_EXTENSIONS


def get_image_type(filename):
    """Get image MIME type from extension."""
    ext = Path(filename).suffix.lstrip('.').lower()
    mime_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'ico': 'image/x-icon',
        'bmp': 'image/bmp',
        'tiff': 'image/tiff',
        'tif': 'image/tiff',
        'heic': 'image/heic',
        'heif': 'image/heif',
        'psd': 'image/vnd.adobe.photoshop',
    }
    return mime_map.get(ext, f'image/{ext}')


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
#git integration - diffs and commit logs
#=============================================================================

def is_git_repository(path):
    """
    Check if path is inside a git repository.
    
    Args:
        path: Path to check
    
    Returns:
        tuple: (is_repo: bool, git_root: str or None, error: str or None)
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip(), None
        return False, None, result.stderr.strip()
    except FileNotFoundError:
        return False, None, "Git is not installed or not in PATH"
    except subprocess.TimeoutExpired:
        return False, None, "Git command timed out"
    except Exception as e:
        return False, None, str(e)


def get_git_diff(path, diff_stat_only=False):
    """
    Get uncommitted changes (both staged and unstaged).
    
    Args:
        path: Path to git repository
        diff_stat_only: If True, return only stat summary
    
    Returns:
        dict: {
            'success': bool,
            'diff': str (full diff),
            'stat': str (diff stat summary),
            'files_changed': int,
            'insertions': int,
            'deletions': int,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'diff': '',
        'stat': '',
        'files_changed': 0,
        'insertions': 0,
        'deletions': 0,
        'error': None
    }
    
    try:
        #get diff stat (summary)
        stat_result = subprocess.run(
            ['git', 'diff', 'HEAD', '--stat'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if stat_result.returncode != 0:
            #might be initial commit with no HEAD, try without HEAD
            stat_result = subprocess.run(
                ['git', 'diff', '--stat'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30
            )
        
        result['stat'] = stat_result.stdout.strip()
        
        #parse stat summary for counts
        if result['stat']:
            lines = result['stat'].split('\n')
            if lines:
                #last line contains summary like "5 files changed, 42 insertions(+), 18 deletions(-)"
                summary_line = lines[-1] if 'changed' in lines[-1] else ''
                if summary_line:
                    #extract numbers
                    files_match = re.search(r'(\d+)\s+files?\s+changed', summary_line)
                    ins_match = re.search(r'(\d+)\s+insertions?', summary_line)
                    del_match = re.search(r'(\d+)\s+deletions?', summary_line)
                    
                    result['files_changed'] = int(files_match.group(1)) if files_match else 0
                    result['insertions'] = int(ins_match.group(1)) if ins_match else 0
                    result['deletions'] = int(del_match.group(1)) if del_match else 0
        
        if not diff_stat_only:
            #get full diff
            diff_result = subprocess.run(
                ['git', 'diff', 'HEAD'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if diff_result.returncode != 0:
                #try without HEAD for initial commits
                diff_result = subprocess.run(
                    ['git', 'diff'],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            
            result['diff'] = diff_result.stdout
        
        result['success'] = True
        
    except subprocess.TimeoutExpired:
        result['error'] = "Git diff command timed out"
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_git_logs(path, count=50, oneline=True):
    """
    Get recent commit logs.
    
    Args:
        path: Path to git repository
        count: Number of commits to retrieve
        oneline: If True, use compact oneline format with date
    
    Returns:
        dict: {
            'success': bool,
            'logs': str,
            'commit_count': int,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'logs': '',
        'commit_count': 0,
        'error': None
    }
    
    try:
        if oneline:
            #compact format: hash date(short) subject
            format_str = '%h %as %s'
            cmd = ['git', 'log', f'-{count}', f'--pretty=format:{format_str}']
        else:
            #medium format with more details
            cmd = ['git', 'log', f'-{count}', '--pretty=medium']
        
        log_result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if log_result.returncode == 0:
            result['logs'] = log_result.stdout.strip()
            #count actual commits returned
            if result['logs']:
                result['commit_count'] = len(result['logs'].split('\n'))
            result['success'] = True
        else:
            result['error'] = log_result.stderr.strip() or "No commits found"
            #might be empty repo
            if 'does not have any commits' in result['error'].lower():
                result['success'] = True
                result['logs'] = '(no commits yet)'
                result['commit_count'] = 0
                result['error'] = None
    
    except subprocess.TimeoutExpired:
        result['error'] = "Git log command timed out"
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_git_logs_with_diffs(path, count=10):
    """
    Get recent commit logs with diff for each commit.
    
    Args:
        path: Path to git repository
        count: Number of commits to retrieve (default 10, keep low due to size)
    
    Returns:
        dict: {
            'success': bool,
            'commits': list of {hash, date, subject, diff},
            'commit_count': int,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'commits': [],
        'commit_count': 0,
        'error': None
    }
    
    try:
        #first get list of commit hashes with metadata
        format_str = '%h||%as||%s'  #hash||date||subject (using || as separator)
        cmd = ['git', 'log', f'-{count}', f'--pretty=format:{format_str}']
        
        log_result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if log_result.returncode != 0:
            result['error'] = log_result.stderr.strip() or "No commits found"
            if 'does not have any commits' in result['error'].lower():
                result['success'] = True
                result['commit_count'] = 0
                result['error'] = None
            return result
        
        if not log_result.stdout.strip():
            result['success'] = True
            result['commit_count'] = 0
            return result
        
        #parse each commit and get its diff
        commits = []
        for line in log_result.stdout.strip().split('\n'):
            if not line or '||' not in line:
                continue
            
            parts = line.split('||', 2)
            if len(parts) < 3:
                continue
            
            commit_hash, date, subject = parts
            
            #get diff for this specific commit
            diff_cmd = ['git', 'show', commit_hash, '--format=', '--patch', '--stat']
            diff_result = subprocess.run(
                diff_cmd,
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            diff_content = ''
            if diff_result.returncode == 0:
                diff_content = diff_result.stdout.strip()
            
            commits.append({
                'hash': commit_hash.strip(),
                'date': date.strip(),
                'subject': subject.strip(),
                'diff': diff_content
            })
        
        result['commits'] = commits
        result['commit_count'] = len(commits)
        result['success'] = True
        
    except subprocess.TimeoutExpired:
        result['error'] = "Git log command timed out"
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_branch_diff(path, target_branch='main'):
    """
    Get diff between current branch and target branch (for PR context).
    Uses three-dot diff to show changes since branching.
    
    Args:
        path: Path to git repository
        target_branch: Branch to compare against (e.g., 'main', 'develop')
    
    Returns:
        dict: {
            'success': bool,
            'diff': str (full diff),
            'stat': str (diff stat summary),
            'current_branch': str,
            'target_branch': str,
            'files_changed': int,
            'insertions': int,
            'deletions': int,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'diff': '',
        'stat': '',
        'current_branch': '',
        'target_branch': target_branch,
        'files_changed': 0,
        'insertions': 0,
        'deletions': 0,
        'error': None
    }
    
    try:
        #get current branch name
        branch_cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        branch_result = subprocess.run(
            branch_cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if branch_result.returncode == 0:
            result['current_branch'] = branch_result.stdout.strip()
        
        #check if target branch exists
        check_cmd = ['git', 'rev-parse', '--verify', target_branch]
        check_result = subprocess.run(
            check_cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if check_result.returncode != 0:
            result['error'] = f"Branch '{target_branch}' not found"
            return result
        
        #get diff stat (summary)
        stat_cmd = ['git', 'diff', f'{target_branch}...HEAD', '--stat']
        stat_result = subprocess.run(
            stat_cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if stat_result.returncode == 0:
            result['stat'] = stat_result.stdout.strip()
            
            #parse stat summary
            if result['stat']:
                lines = result['stat'].split('\n')
                if lines:
                    summary_line = lines[-1] if 'changed' in lines[-1] else ''
                    if summary_line:
                        files_match = re.search(r'(\d+)\s+files?\s+changed', summary_line)
                        ins_match = re.search(r'(\d+)\s+insertions?', summary_line)
                        del_match = re.search(r'(\d+)\s+deletions?', summary_line)
                        
                        result['files_changed'] = int(files_match.group(1)) if files_match else 0
                        result['insertions'] = int(ins_match.group(1)) if ins_match else 0
                        result['deletions'] = int(del_match.group(1)) if del_match else 0
        
        #get full diff
        diff_cmd = ['git', 'diff', f'{target_branch}...HEAD']
        diff_result = subprocess.run(
            diff_cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if diff_result.returncode == 0:
            result['diff'] = diff_result.stdout
            result['success'] = True
        else:
            result['error'] = diff_result.stderr.strip() or "Failed to get branch diff"
    
    except subprocess.TimeoutExpired:
        result['error'] = "Git diff command timed out"
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_branch_diff(path, target_branch='main'):
    """
    Get diff between current branch and target branch (for PR review).
    Uses three-dot diff to show changes since branching.
    
    Args:
        path: Path to git repository
        target_branch: Branch to compare against (default: main)
    
    Returns:
        dict: {
            'success': bool,
            'diff': str,
            'stat': str,
            'current_branch': str,
            'target_branch': str,
            'files_changed': int,
            'insertions': int,
            'deletions': int,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'diff': '',
        'stat': '',
        'current_branch': '',
        'target_branch': target_branch,
        'files_changed': 0,
        'insertions': 0,
        'deletions': 0,
        'error': None
    }
    
    try:
        #get current branch name
        branch_result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if branch_result.returncode == 0:
            result['current_branch'] = branch_result.stdout.strip()
        
        #check if target branch exists
        check_branch = subprocess.run(
            ['git', 'rev-parse', '--verify', target_branch],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if check_branch.returncode != 0:
            result['error'] = f"Branch '{target_branch}' not found"
            return result
        
        #get diff stat
        stat_result = subprocess.run(
            ['git', 'diff', f'{target_branch}...HEAD', '--stat'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if stat_result.returncode == 0:
            result['stat'] = stat_result.stdout.strip()
            
            #parse stat for counts
            if result['stat']:
                lines = result['stat'].split('\n')
                summary_line = lines[-1] if lines and 'changed' in lines[-1] else ''
                if summary_line:
                    import re
                    files_match = re.search(r'(\d+)\s+files?\s+changed', summary_line)
                    ins_match = re.search(r'(\d+)\s+insertions?', summary_line)
                    del_match = re.search(r'(\d+)\s+deletions?', summary_line)
                    
                    result['files_changed'] = int(files_match.group(1)) if files_match else 0
                    result['insertions'] = int(ins_match.group(1)) if ins_match else 0
                    result['deletions'] = int(del_match.group(1)) if del_match else 0
        
        #get full diff
        diff_result = subprocess.run(
            ['git', 'diff', f'{target_branch}...HEAD'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if diff_result.returncode == 0:
            result['diff'] = diff_result.stdout
            result['success'] = True
        else:
            result['error'] = diff_result.stderr.strip() or "Failed to get branch diff"
    
    except subprocess.TimeoutExpired:
        result['error'] = "Git diff command timed out"
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_git_changed_files(path):
    """
    Get list of git-modified files (staged, unstaged, and untracked).
    
    Args:
        path: Path to git repository
    
    Returns:
        dict: {
            'success': bool,
            'files': list of relative file paths,
            'staged': list of staged files,
            'unstaged': list of unstaged files,
            'untracked': list of untracked files,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'files': [],
        'staged': [],
        'unstaged': [],
        'untracked': [],
        'error': None
    }
    
    try:
        #git status --porcelain gives us all changed files
        #format: XY filename
        #X = staged status, Y = unstaged status
        #?? = untracked
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if status_result.returncode != 0:
            result['error'] = status_result.stderr.strip()
            return result
        
        all_files = set()
        
        for line in status_result.stdout.strip().split('\n'):
            if not line:
                continue
            
            #parse status codes
            staged_status = line[0]
            unstaged_status = line[1]
            filepath = line[3:].strip()
            
            #handle renamed files (format: "old -> new")
            if ' -> ' in filepath:
                filepath = filepath.split(' -> ')[1]
            
            #remove quotes if present
            if filepath.startswith('"') and filepath.endswith('"'):
                filepath = filepath[1:-1]
            
            all_files.add(filepath)
            
            if staged_status == '?' and unstaged_status == '?':
                result['untracked'].append(filepath)
            else:
                if staged_status != ' ' and staged_status != '?':
                    result['staged'].append(filepath)
                if unstaged_status != ' ' and unstaged_status != '?':
                    result['unstaged'].append(filepath)
        
        result['files'] = sorted(list(all_files))
        result['success'] = True
        
    except subprocess.TimeoutExpired:
        result['error'] = "Git status command timed out"
    except Exception as e:
        result['error'] = str(e)
    
    return result



#=============================================================================
#images section - list image files without content
#=============================================================================

def create_images_section(image_files, base_path):
    """
    Create XML section listing image files (metadata only, no content).
    
    Args:
        image_files: List of Path objects for image files
        base_path: Base path for relative path calculation
    
    Returns:
        str: XML section string
    """
    if not image_files:
        return ''
    
    lines = [f'  <images count="{len(image_files)}">']
    
    for img_path in sorted(image_files, key=lambda p: str(p).lower()):
        try:
            relative_path = img_path.relative_to(base_path)
            relative_str = str(relative_path).replace('\\', '/')
        except ValueError:
            relative_str = img_path.name
        
        filename = img_path.name
        img_type = get_image_type(filename)
        
        try:
            size_bytes = img_path.stat().st_size
        except Exception:
            size_bytes = 0
        
        lines.append(f'    <image file="{filename}" path="{relative_str}" type="{img_type}" size_bytes="{size_bytes}"/>')
    
    lines.append('  </images>')
    
    return '\n'.join(lines)


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


def write_chunk(output_file, root_tag, content_lines, folder_path, file_count, start_num, recursive, compress=False, chunk_num=None, total_chunks=None, tree_section=None, images_section=None):
    """Write a single chunk file."""
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<{root_tag}>',
        create_metadata(
            folder_path, file_count, start_num, recursive, compress, 
            chunk_num, total_chunks, 
            include_tree=(tree_section is not None)
        ),
    ]
    
    #add project structure tree if provided (only in first chunk)
    if tree_section:
        xml_lines.append(tree_section)
    
    #add images section if provided (only in first chunk)
    if images_section:
        xml_lines.append(images_section)
    
    xml_lines.extend(content_lines)
    xml_lines.append(f'</{root_tag}>')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(xml_lines))


def write_git_file(output_file, folder_path, diff_result=None, logs_with_diffs_result=None, branch_diff_result=None, commits_count=10):
    """Write git information to a separate file."""
    timestamp = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<git_context>',
        '  <metadata>',
        f'    <source_folder>{folder_path}</source_folder>',
        f'    <generated_at>{timestamp}</generated_at>',
    ]
    
    if diff_result and diff_result.get('success'):
        xml_lines.append(f'    <uncommitted_diffs_included>true</uncommitted_diffs_included>')
    
    if branch_diff_result and branch_diff_result.get('success'):
        xml_lines.append(f'    <branch_diff_included>true</branch_diff_included>')
        xml_lines.append(f'    <current_branch>{branch_diff_result.get("current_branch", "")}</current_branch>')
        xml_lines.append(f'    <target_branch>{branch_diff_result.get("target_branch", "")}</target_branch>')
    
    if logs_with_diffs_result and logs_with_diffs_result.get('success'):
        xml_lines.append(f'    <commits_included>true</commits_included>')
        xml_lines.append(f'    <commits_count>{commits_count}</commits_count>')
    
    xml_lines.append('  </metadata>')
    
    #add branch diff section (for PR review)
    if branch_diff_result and branch_diff_result.get('success'):
        current = branch_diff_result.get('current_branch', '')
        target = branch_diff_result.get('target_branch', '')
        files = branch_diff_result.get('files_changed', 0)
        ins = branch_diff_result.get('insertions', 0)
        dels = branch_diff_result.get('deletions', 0)
        
        xml_lines.append(f'  <branch_diff current="{current}" target="{target}" files_changed="{files}" insertions="{ins}" deletions="{dels}">')
        xml_lines.append(f'    <stat><![CDATA[')
        xml_lines.append(branch_diff_result.get('stat', ''))
        xml_lines.append('    ]]></stat>')
        xml_lines.append('    <diff><![CDATA[')
        diff_content = branch_diff_result.get('diff', '').strip()
        xml_lines.append(diff_content if diff_content else 'No changes between branches')
        xml_lines.append('    ]]></diff>')
        xml_lines.append('  </branch_diff>')
    elif branch_diff_result and branch_diff_result.get('error'):
        xml_lines.append(f'  <branch_diff error="{branch_diff_result["error"]}"/>')
    
    #add uncommitted diffs section
    if diff_result and diff_result.get('success'):
        files = diff_result.get('files_changed', 0)
        ins = diff_result.get('insertions', 0)
        dels = diff_result.get('deletions', 0)
        
        xml_lines.append(f'  <uncommitted_changes files_changed="{files}" insertions="{ins}" deletions="{dels}">')
        
        diff_content = diff_result.get('diff', '').strip()
        if diff_content:
            xml_lines.append('    <![CDATA[')
            xml_lines.append(diff_content)
            xml_lines.append('    ]]>')
        else:
            xml_lines.append('    <![CDATA[No uncommitted changes]]>')
        
        xml_lines.append('  </uncommitted_changes>')
    elif diff_result and diff_result.get('error'):
        xml_lines.append(f'  <uncommitted_changes error="{diff_result["error"]}"/>')
    
    #add commit history with diffs
    if logs_with_diffs_result and logs_with_diffs_result.get('success'):
        commits = logs_with_diffs_result.get('commits', [])
        count = len(commits)
        xml_lines.append(f'  <commits count="{count}">')
        
        for commit in commits:
            hash_val = commit.get('hash', '')
            date_val = commit.get('date', '')
            subject_val = commit.get('subject', '').replace('"', '&quot;')
            diff_val = commit.get('diff', '')
            
            xml_lines.append(f'    <commit hash="{hash_val}" date="{date_val}" subject="{subject_val}">')
            xml_lines.append('      <![CDATA[')
            xml_lines.append(diff_val if diff_val else '(no changes)')
            xml_lines.append('      ]]>')
            xml_lines.append('    </commit>')
        
        xml_lines.append('  </commits>')
    elif logs_with_diffs_result and logs_with_diffs_result.get('error'):
        xml_lines.append(f'  <commits error="{logs_with_diffs_result["error"]}"/>')
    
    xml_lines.append('</git_context>')
    
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
  %(prog)s /path/to/project --uncommitted
  %(prog)s /path/to/project --commits 5
  %(prog)s /path/to/project --changed-only --uncommitted
  %(prog)s /path/to/project --pr main --include-tree

PR review mode (--pr <target>):
  - Shows all changes between current branch and target (e.g., main)
  - Perfect for AI-assisted code review before merging
  - Combines well with --include-tree for full context
  - Example: --pr main --uncommitted

Changed-only mode (--changed-only):
  - Only process git-modified files (staged, unstaged, untracked)
  - Perfect for focusing AI on current work in progress
  - Requires git repository, falls back to all files otherwise

Auto-excluded folders (always applied):
  - build/, out/, bin/, .gradle/, .idea/, node_modules/
  - __pycache__/, .git/, target/, dist/, .cache/
  - venv/, .venv/, Pods/, DerivedData/, generated/

Image handling:
  - Image files are automatically detected and listed separately
  - Only metadata is included (filename, path, type, size)
  - No image content is processed (saves tokens)
  - Supported: png, jpg, jpeg, gif, webp, svg, ico, bmp, tiff

Commit history (--commits):
  - Shows full diff for each commit in history
  - Use --commits N to limit (default: 10)
  - Useful for understanding recent changes

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

Git integration:
  - --pr <branch>: PR diff against target branch  
  - --uncommitted: Working directory changes
  - --commits: Commit history with diffs
  - Saved to separate file: {prefix}_git.text

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
        '--uncommitted',
        action='store_true',
        help='Include git diff (uncommitted changes) in output'
    )
    parser.add_argument(
        '--commits',
        type=int,
        nargs='?',
        const=10,
        default=None,
        metavar='COUNT',
        help='Include commit history with diffs (default: 10 commits)'
    )
    parser.add_argument(
        '--pr',
        type=str,
        metavar='BRANCH',
        help='Show diff against target branch for PR review (e.g., --pr main)'
    )
    parser.add_argument(
        '--changed-only',
        action='store_true',
        help='Only include git-modified files (staged, unstaged, untracked)'
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
    
    #always exclude build folders
    original_count = len(files)
    files = [f for f in files if not is_build_folder(f)]
    build_excluded = original_count - len(files)
    if build_excluded > 0:
        print(f"Excluded {build_excluded} files from build/generated folders")
    
    #apply --changed-only filter if requested
    changed_only_applied = False
    if args.changed_only:
        is_repo, git_root, git_error = is_git_repository(folder_path)
        if not is_repo:
            print(f"⚠️  Git: Not a git repository ({git_error or 'unknown error'})")
            print("   --changed-only requires git, processing all files instead")
        else:
            changed_result = get_git_changed_files(folder_path)
            if changed_result['success']:
                changed_files_set = set(changed_result['files'])
                #filter to only changed files
                files_before = len(files)
                files = [f for f in files if any(
                    str(f).replace('\\', '/').endswith(cf) or 
                    cf in str(f).replace('\\', '/')
                    for cf in changed_files_set
                )]
                changed_only_applied = True
                print(f"Changed files: {len(changed_result['staged'])} staged, {len(changed_result['unstaged'])} unstaged, {len(changed_result['untracked'])} untracked")
                print(f"Filtered to {len(files)} changed files (from {files_before})")
            else:
                print(f"⚠️  Git status failed: {changed_result.get('error', 'Unknown error')}")
                print("   Processing all files instead")
    
    #apply filters
    if args.filter_ext:
        filter_exts = [e.lstrip('.').lower() for e in args.filter_ext]
        files = [f for f in files if f.suffix.lstrip('.').lower() in filter_exts]
    
    if args.exclude_ext:
        exclude_exts = [e.lstrip('.').lower() for e in args.exclude_ext]
        files = [f for f in files if f.suffix.lstrip('.').lower() not in exclude_exts]
    
    if args.max_files:
        files = files[:args.max_files]
    
    #separate images from code files
    image_files = [f for f in files if is_image_file(f)]
    code_files = [f for f in files if not is_image_file(f)]
    
    if image_files:
        print(f"Found {len(image_files)} image files (will list metadata only)")
    
    #use code_files for processing, keep image_files for metadata section
    files = code_files
    
    #check if any files found
    if not files and not image_files:
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
        #include both code and image files in tree
        all_files_for_tree = files + image_files
        tree_content = generate_directory_tree(all_files_for_tree, folder_path, args.tree_depth)
        total_dirs = count_directories(all_files_for_tree, folder_path)
        tree_section = create_project_structure_section(tree_content, len(all_files_for_tree), total_dirs)
        tree_tokens = estimate_tokens(tree_section)
        print(f"Directory tree: {total_dirs} directories (~{tree_tokens:,} tokens)")
    
    #generate images section (always if images exist)
    images_section = None
    images_tokens = 0
    if image_files:
        images_section = create_images_section(image_files, folder_path)
        images_tokens = estimate_tokens(images_section)
        print(f"Images section: {len(image_files)} images (~{images_tokens:,} tokens)")
    
    #generate git sections if requested
    git_file_written = False
    diff_result = None
    logs_with_diffs_result = None
    branch_diff_result = None
    
    if args.uncommitted or args.commits or args.pr:
        is_repo, git_root, git_error = is_git_repository(folder_path)
        
        if not is_repo:
            print(f"⚠️  Git: Not a git repository ({git_error or 'unknown error'})")
            print("   Skipping git diffs and logs")
        else:
            print(f"Git repository: {git_root}")
            
            #branch diff for PR review
            if args.pr:
                branch_diff_result = get_branch_diff(folder_path, args.pr)
                if branch_diff_result['success']:
                    current = branch_diff_result['current_branch']
                    target = branch_diff_result['target_branch']
                    bd_files = branch_diff_result['files_changed']
                    ins = branch_diff_result['insertions']
                    dels = branch_diff_result['deletions']
                    print(f"Branch diff: {current} vs {target} ({bd_files} files, +{ins}/-{dels})")
                else:
                    print(f"⚠️  Branch diff: {branch_diff_result.get('error', 'Unknown error')}")
            
            if args.uncommitted:
                diff_result = get_git_diff(folder_path)
                if diff_result['success']:
                    if diff_result['files_changed'] > 0:
                        print(f"Uncommitted changes: {diff_result['files_changed']} files changed, +{diff_result['insertions']}/-{diff_result['deletions']}")
                    else:
                        print("Uncommitted changes: None")
                else:
                    print(f"⚠️  Git diffs: {diff_result.get('error', 'Unknown error')}")
            
            #commit history with diffs
            if args.commits:
                logs_with_diffs_result = get_git_logs_with_diffs(folder_path, args.commits)
                if logs_with_diffs_result['success']:
                    print(f"Commits with diffs: {logs_with_diffs_result['commit_count']} commits")
                else:
                    print(f"⚠️  Commits: {logs_with_diffs_result.get('error', 'Unknown error')}")
    
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
    first_chunk_overhead = base_overhead_tokens + tree_tokens + images_tokens
    
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
        
        #determine overhead for current chunk (first chunk may include tree + git)
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
    
    #write git file if we have git data
    git_output_file = None
    if diff_result or logs_with_diffs_result or branch_diff_result:
        has_valid_git_data = (
            (diff_result and diff_result.get('success')) or
            (logs_with_diffs_result and logs_with_diffs_result.get('success')) or
            (branch_diff_result and branch_diff_result.get('success'))
        )
        if has_valid_git_data:
            git_output_file = f'{args.output_prefix}_git.text'
            write_git_file(git_output_file, args.folder_path, diff_result, logs_with_diffs_result, branch_diff_result, args.commits or 10)
            git_tokens = estimate_tokens(open(git_output_file).read())
            print(f"\n✅ Created {git_output_file}")
            git_includes = []
            if branch_diff_result and branch_diff_result.get('success'):
                git_includes.append(f"PR diff: {branch_diff_result['current_branch']} vs {branch_diff_result['target_branch']} ({branch_diff_result['files_changed']} files)")
            if diff_result and diff_result.get('success'):
                git_includes.append(f"uncommitted ({diff_result['files_changed']} files)")
            if logs_with_diffs_result and logs_with_diffs_result.get('success'):
                git_includes.append(f"commits ({logs_with_diffs_result['commit_count']} with diffs)")
            print(f"   Contains: {', '.join(git_includes)}")
            print(f"   Estimated tokens: ~{git_tokens:,}")
    
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
            tree_section=tree_section,
            images_section=images_section
        )
        print(f"\n✅ Created {output_file}")
        print(f"   Files: {chunks[0]['file_count']}")
        includes = []
        if args.include_tree:
            includes.append('directory tree')
        if images_section:
            includes.append(f'{len(image_files)} images')
        if includes:
            print(f"   Includes: {", ".join(includes)}")
        print(f"   Estimated tokens: ~{estimate_tokens(open(output_file).read()):,}")
    else:
        #multiple chunks
        for i, chunk in enumerate(chunks, 1):
            output_file = f'{args.output_prefix}{compress_suffix}_part{i}_of_{total_chunks}.text'
            #only include tree and images in first chunk
            chunk_tree = tree_section if i == 1 else None
            chunk_images = images_section if i == 1 else None
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
                tree_section=chunk_tree,
                images_section=chunk_images
            )
            tokens = estimate_tokens(open(output_file).read())
            print(f"\n✅ Created {output_file}")
            print(f"   Files: {chunk['file_count']}")
            print(f"   Code tags: <code{chunk['start_num']}> to <code{chunk['start_num'] + chunk['file_count'] - 1}>")
            if i == 1:
                includes = []
                if args.include_tree:
                    includes.append('directory tree')
                if images_section:
                    includes.append(f'{len(image_files)} images')
                if includes:
                    print(f"   Includes: {", ".join(includes)}")
            print(f"   Estimated tokens: ~{tokens:,}")
    
    print(f"\n📊 Summary:")
    print(f"   Total code files: {len(files)}")
    if image_files:
        print(f"   Total images: {len(image_files)} (metadata only)")
    print(f"   Total chunks created: {total_chunks}")
    if git_output_file:
        print(f"   Git file: {git_output_file}")
    print(f"   Recursive mode: {args.recursive}")
    print(f"   Compress mode: {args.compress}")
    print(f"   Changed only: {args.changed_only}")
    print(f"   Directory tree: {args.include_tree}")
    if args.pr:
        print(f"   PR diff: vs {args.pr}")
    print(f"   Uncommitted: {args.uncommitted}")
    print(f"   Commits: {args.commits if args.commits else False}")
    
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
    
    if git_output_file:
        print(f"\n💡 Git context is in separate file: {git_output_file}")
        print(f"   Upload alongside code files for full context")


if __name__ == '__main__':
    main()
