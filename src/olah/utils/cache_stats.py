# coding=utf-8
# Copyright 2024 XiaHan
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from olah.utils.disk_utils import get_folder_size, convert_bytes_to_human_readable


class CacheStats:
    """Class for collecting and analyzing cache statistics"""
    
    def __init__(self, repos_path: str):
        self.repos_path = Path(repos_path)
        self.cache_dirs = {
            "models": self.repos_path / "api" / "models",
            "datasets": self.repos_path / "api" / "datasets", 
            "spaces": self.repos_path / "api" / "spaces",
            "files": self.repos_path / "files",
            "lfs": self.repos_path / "lfs"
        }
    
    def get_cache_overview(self) -> Dict[str, Any]:
        """Returns overall cache statistics overview"""
        total_size = 0
        total_files = 0
        repo_counts = {}
        
        for repo_type, cache_dir in self.cache_dirs.items():
            if cache_dir.exists():
                size = get_folder_size(str(cache_dir))
                file_count = self._count_files(cache_dir)
                total_size += size
                total_files += file_count
                repo_counts[repo_type] = {
                    "size": size,
                    "size_human": convert_bytes_to_human_readable(size),
                    "file_count": file_count,
                    "repo_count": self._count_repos(cache_dir)
                }
        
        return {
            "total_size": total_size,
            "total_size_human": convert_bytes_to_human_readable(total_size),
            "total_files": total_files,
            "repo_counts": repo_counts,
            "cache_dirs": {k: str(v) for k, v in self.cache_dirs.items()},
            "last_updated": datetime.now().isoformat()
        }
    
    def get_cached_repos(self, repo_type: Optional[str] = None, 
                         limit: Optional[int] = None,
                         sort_by: str = "size",
                         sort_order: str = "desc") -> List[Dict[str, Any]]:
        """Returns list of cached repositories"""
        repos = []
        
        if repo_type:
            repo_types = [repo_type]
        else:
            repo_types = ["models", "datasets", "spaces"]
        
        for rt in repo_types:
            cache_dir = self.cache_dirs.get(rt)
            if not cache_dir or not cache_dir.exists():
                continue
                
            for org_dir in cache_dir.iterdir():
                if not org_dir.is_dir():
                    continue
                    
                for repo_dir in org_dir.iterdir():
                    if not repo_dir.is_dir():
                        continue
                        
                    repo_info = self._get_repo_info(rt, org_dir.name, repo_dir.name, repo_dir)
                    if repo_info:
                        repos.append(repo_info)
        
        # Sorting
        if sort_by == "size":
            repos.sort(key=lambda x: x["size"], reverse=(sort_order == "desc"))
        elif sort_by == "last_access":
            repos.sort(key=lambda x: x["last_access"], reverse=(sort_order == "desc"))
        elif sort_by == "last_modified":
            repos.sort(key=lambda x: x["last_modified"], reverse=(sort_order == "desc"))
        elif sort_by == "name":
            repos.sort(key=lambda x: x["full_name"], reverse=(sort_order == "desc"))
        
        # Limit results
        if limit:
            repos = repos[:limit]
            
        return repos
    
    def get_repo_details(self, repo_type: str, org: str, repo: str) -> Optional[Dict[str, Any]]:
        """Returns detailed information for a specific repository"""
        cache_dir = self.cache_dirs.get(repo_type)
        if not cache_dir or not cache_dir.exists():
            return None
            
        repo_path = cache_dir / org / repo
        if not repo_path.exists():
            return None
            
        return self._get_repo_info(repo_type, org, repo, repo_path, detailed=True)
    
    def search_repos(self, query: str, repo_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search repositories"""
        all_repos = self.get_cached_repos(repo_type)
        query_lower = query.lower()
        
        results = []
        for repo in all_repos:
            if (query_lower in repo["full_name"].lower() or 
                query_lower in repo.get("description", "").lower()):
                results.append(repo)
        
        return results
    
    def get_cache_efficiency(self) -> Dict[str, Any]:
        """Analyzes cache efficiency"""
        total_size = 0
        total_files = 0
        access_times = []
        
        for cache_dir in self.cache_dirs.values():
            if cache_dir.exists():
                size = get_folder_size(str(cache_dir))
                total_size += size
                total_files += self._count_files(cache_dir)
                
                # Analyze access times
                for file_path in cache_dir.rglob("*"):
                    if file_path.is_file():
                        try:
                            atime = datetime.fromtimestamp(file_path.stat().st_atime)
                            access_times.append(atime)
                        except (OSError, ValueError):
                            continue
        
        # Analyze access patterns
        now = datetime.now()
        recent_access = sum(1 for atime in access_times if now - atime < timedelta(days=7))
        old_access = sum(1 for atime in access_times if now - atime > timedelta(days=30))
        
        return {
            "total_size": total_size,
            "total_size_human": convert_bytes_to_human_readable(total_size),
            "total_files": total_files,
            "recent_access_count": recent_access,
            "old_access_count": old_access,
            "access_efficiency": (recent_access / total_files * 100) if total_files > 0 else 0,
            "last_updated": now.isoformat()
        }
    
    def _count_files(self, directory: Path) -> int:
        """Returns the number of files in a directory"""
        try:
            return sum(1 for _ in directory.rglob("*") if _.is_file())
        except (OSError, PermissionError):
            return 0
    
    def _count_repos(self, directory: Path) -> int:
        """Returns the number of repositories in a directory"""
        try:
            count = 0
            for org_dir in directory.iterdir():
                if org_dir.is_dir():
                    for repo_dir in org_dir.iterdir():
                        if repo_dir.is_dir():
                            count += 1
            return count
        except (OSError, PermissionError):
            return 0
    
    def _get_repo_info(self, repo_type: str, org: str, repo: str, 
                       repo_path: Path, detailed: bool = False) -> Optional[Dict[str, Any]]:
        """Extracts repository information"""
        try:
            stat = repo_path.stat()
            size = get_folder_size(str(repo_path))
            
            repo_info = {
                "repo_type": repo_type,
                "org": org,
                "repo": repo,
                "full_name": f"{org}/{repo}",
                "size": size,
                "size_human": convert_bytes_to_human_readable(size),
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "last_access": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "path": str(repo_path)
            }
            
            if detailed:
                repo_info.update({
                    "file_count": self._count_files(repo_path),
                    "git_info": self._get_git_info(repo_path),
                    "description": self._get_repo_description(repo_path)
                })
            
            return repo_info
            
        except (OSError, PermissionError):
            return None
    
    def _get_git_info(self, repo_path: Path) -> Optional[Dict[str, Any]]:
        """Extracts Git repository information"""
        try:
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                return None
                
            # Extract only basic Git info (minimize GitPython dependency)
            head_file = git_dir / "HEAD"
            if head_file.exists():
                with open(head_file, 'r') as f:
                    head_content = f.read().strip()
                    if head_content.startswith('ref: refs/heads/'):
                        branch = head_content.replace('ref: refs/heads/', '')
                    else:
                        branch = head_content[:8]  # Partial commit hash
                
                return {
                    "branch": branch,
                    "is_git_repo": True
                }
        except (OSError, PermissionError):
            pass
        
        return None
    
    def _get_repo_description(self, repo_path: Path) -> str:
        """Extracts repository description (from README.md)"""
        readme_files = ["README.md", "readme.md", "README.txt", "readme.txt"]
        
        for readme_name in readme_files:
            readme_path = repo_path / readme_name
            if readme_path.exists():
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Return only first 200 characters
                        return content[:200].strip()
                except (OSError, UnicodeDecodeError):
                    continue
        
        return ""
