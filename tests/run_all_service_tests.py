#!/usr/bin/env python3
"""
Run all service tests after converting from async to sync
"""
import sys
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.logger import logger

def run_test(test_script: str) -> bool:
    """Run a single test script"""
    logger.info(f"🚀 Running {test_script}...")
    
    try:
        result = subprocess.run(
            ["uv", "run", test_script],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout per test
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {test_script} PASSED")
            return True
        else:
            logger.error(f"❌ {test_script} FAILED")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ {test_script} TIMED OUT")
        return False
    except Exception as e:
        logger.error(f"💥 {test_script} ERROR: {str(e)}")
        return False

def main():
    """Run all service tests"""
    logger.info("🧪 Running all service tests...")
    
    test_scripts = [
        "tests/test_gen_service.py",      # Start with GenService (most likely to work)
        "tests/test_chat_service.py",
        "tests/test_creative_service.py",
        "tests/test_agent_service.py",
        "tests/test_draw_service.py",
    ]
    
    results = {}
    
    for test_script in test_scripts:
        test_name = Path(test_script).stem
        results[test_name] = run_test(test_script)
    
    # Summary
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    logger.info("\n📊 Test Results Summary:")
    logger.info(f"✅ Passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    if passed == total:
        logger.info("🎉 All service tests PASSED!")
    else:
        logger.error(f"💥 {total - passed} service tests FAILED!")
        logger.error("🔧 Please check the failed tests for issues.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
