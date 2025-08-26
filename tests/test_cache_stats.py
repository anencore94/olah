# coding=utf-8
# Copyright 2024 XiaHan
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from olah.utils.cache_stats import CacheStats


class TestCacheStats:
    """Test for CacheStats class"""
    
    @pytest.fixture
    def temp_repos_path(self):
        """Creates temporary repository path"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure
            os.makedirs(os.path.join(temp_dir, "api", "models", "test_org", "test_model"))
            os.makedirs(os.path.join(temp_dir, "api", "datasets", "test_org", "test_dataset"))
            os.makedirs(os.path.join(temp_dir, "files"))
            os.makedirs(os.path.join(temp_dir, "lfs"))
            
            # Create test files
            with open(os.path.join(temp_dir, "api", "models", "test_org", "test_model", "test.txt"), "w") as f:
                f.write("test content")
            
            with open(os.path.join(temp_dir, "api", "datasets", "test_org", "test_dataset", "data.txt"), "w") as f:
                f.write("dataset content")
            
            yield temp_dir
    
    def test_init(self, temp_repos_path):
        """Test initialization"""
        cache_stats = CacheStats(temp_repos_path)
        assert cache_stats.repos_path == Path(temp_repos_path)
        assert "models" in cache_stats.cache_dirs
        assert "datasets" in cache_stats.cache_dirs
        assert "spaces" in cache_stats.cache_dirs
        assert "files" in cache_stats.cache_dirs
        assert "lfs" in cache_stats.cache_dirs
    
    def test_get_cache_overview(self, temp_repos_path):
        """Test cache overview statistics"""
        cache_stats = CacheStats(temp_repos_path)
        overview = cache_stats.get_cache_overview()
        
        assert "total_size" in overview
        assert "total_files" in overview
        assert "repo_counts" in overview
        assert "last_updated" in overview
        
        # Verify statistics by repository type
        assert "models" in overview["repo_counts"]
        assert "datasets" in overview["repo_counts"]
        assert overview["repo_counts"]["models"]["repo_count"] == 1
        assert overview["repo_counts"]["datasets"]["repo_count"] == 1
    
    def test_get_cached_repos(self, temp_repos_path):
        """Test cached repository list"""
        cache_stats = CacheStats(temp_repos_path)
        repos = cache_stats.get_cached_repos()
        
        assert len(repos) == 2  # models + datasets
        
        # Verify repository information structure
        for repo in repos:
            assert "repo_type" in repo
            assert "org" in repo
            assert "repo" in repo
            assert "full_name" in repo
            assert "size" in repo
            assert "size_human" in repo
            assert "last_modified" in repo
            assert "last_access" in repo
            assert "path" in repo
    
    def test_get_cached_repos_with_filters(self, temp_repos_path):
        """Test filtered repository list"""
        cache_stats = CacheStats(temp_repos_path)
        
        # Filter by repository type
        models = cache_stats.get_cached_repos(repo_type="models")
        assert len(models) == 1
        assert models[0]["repo_type"] == "models"
        
        datasets = cache_stats.get_cached_repos(repo_type="datasets")
        assert len(datasets) == 1
        assert datasets[0]["repo_type"] == "datasets"
        
        # Test sorting
        repos_by_size = cache_stats.get_cached_repos(sort_by="size", sort_order="desc")
        assert len(repos_by_size) == 2
        
        # Test limiting
        limited_repos = cache_stats.get_cached_repos(limit=1)
        assert len(limited_repos) == 1
    
    def test_get_repo_details(self, temp_repos_path):
        """Test detailed information for specific repository"""
        cache_stats = CacheStats(temp_repos_path)
        repo_info = cache_stats.get_repo_details("models", "test_org", "test_model")
        
        assert repo_info is not None
        assert repo_info["repo_type"] == "models"
        assert repo_info["org"] == "test_org"
        assert repo_info["repo"] == "test_model"
        assert repo_info["full_name"] == "test_org/test_model"
        
        # Detailed information should be included
        assert "file_count" in repo_info
        assert "git_info" in repo_info
        assert "description" in repo_info
    
    def test_get_repo_details_not_found(self, temp_repos_path):
        """Test detailed information for non-existent repository"""
        cache_stats = CacheStats(temp_repos_path)
        repo_info = cache_stats.get_repo_details("models", "nonexistent", "repo")
        
        assert repo_info is None
    
    def test_search_repos(self, temp_repos_path):
        """Test repository search"""
        cache_stats = CacheStats(temp_repos_path)
        
        # Full search
        results = cache_stats.search_repos("test")
        assert len(results) == 2
        
        # Search by repository type
        model_results = cache_stats.search_repos("test", repo_type="models")
        assert len(model_results) == 1
        assert model_results[0]["repo_type"] == "models"
        
        # Non-existent search term
        no_results = cache_stats.search_repos("nonexistent")
        assert len(no_results) == 0
    
    def test_get_cache_efficiency(self, temp_repos_path):
        """Test cache efficiency analysis"""
        cache_stats = CacheStats(temp_repos_path)
        efficiency = cache_stats.get_cache_efficiency()
        
        assert "total_size" in efficiency
        assert "total_files" in efficiency
        assert "recent_access_count" in efficiency
        assert "old_access_count" in efficiency
        assert "access_efficiency" in efficiency
        assert "last_updated" in efficiency
        
        # Efficiency should be between 0-100
        assert 0 <= efficiency["access_efficiency"] <= 100
    
    def test_count_files(self, temp_repos_path):
        """Test file count calculation"""
        cache_stats = CacheStats(temp_repos_path)
        
        # File count in models directory
        models_dir = Path(temp_repos_path) / "api" / "models"
        file_count = cache_stats._count_files(models_dir)
        assert file_count > 0
    
    def test_count_repos(self, temp_repos_path):
        """Test repository count calculation"""
        cache_stats = CacheStats(temp_repos_path)
        
        # Repository count in models directory
        models_dir = Path(temp_repos_path) / "api" / "models"
        repo_count = cache_stats._count_repos(models_dir)
        assert repo_count == 1
    
    def test_get_repo_info(self, temp_repos_path):
        """Test repository information extraction"""
        cache_stats = CacheStats(temp_repos_path)
        repo_path = Path(temp_repos_path) / "api" / "models" / "test_org" / "test_model"
        
        # Basic information only
        repo_info = cache_stats._get_repo_info("models", "test_org", "test_model", repo_path, detailed=False)
        assert "file_count" not in repo_info
        assert "git_info" not in repo_info
        assert "description" not in repo_info
        
        # With detailed information
        repo_info_detailed = cache_stats._get_repo_info("models", "test_org", "test_model", repo_path, detailed=True)
        assert "file_count" in repo_info_detailed
        assert "git_info" in repo_info_detailed
        assert "description" in repo_info_detailed
    
    def test_get_git_info(self, temp_repos_path):
        """Test Git repository information extraction"""
        cache_stats = CacheStats(temp_repos_path)
        repo_path = Path(temp_repos_path) / "api" / "models" / "test_org" / "test_model"
        
        # When Git repository doesn't exist
        git_info = cache_stats._get_git_info(repo_path)
        assert git_info is None
        
        # Create Git repository and test
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main")
        
        git_info = cache_stats._get_git_info(repo_path)
        assert git_info is not None
        assert git_info["is_git_repo"] is True
        assert git_info["branch"] == "main"
    
    def test_get_repo_description(self, temp_repos_path):
        """Test repository description extraction"""
        cache_stats = CacheStats(temp_repos_path)
        repo_path = Path(temp_repos_path) / "api" / "models" / "test_org" / "test_model"
        
        # When README file doesn't exist
        description = cache_stats._get_repo_description(repo_path)
        assert description == ""
        
        # Create README file and test
        readme_path = repo_path / "README.md"
        readme_path.write_text("This is a test model repository")
        
        description = cache_stats._get_repo_description(repo_path)
        assert "test model repository" in description
    
    def test_error_handling(self):
        """Test error handling"""
        # Non-existent path
        cache_stats = CacheStats("/nonexistent/path")
        
        # Should not cause errors
        overview = cache_stats.get_cache_overview()
        assert overview["total_size"] == 0
        assert overview["total_files"] == 0
        
        repos = cache_stats.get_cached_repos()
        assert len(repos) == 0


if __name__ == "__main__":
    pytest.main([__file__])
