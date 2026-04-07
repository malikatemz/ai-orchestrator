#!/usr/bin/env python
"""
Full-Stack Test Suite Runner
Tests backend, frontend, security, and integration

Coverage:
- Backend unit tests
- Backend security tests  
- Frontend type checking
- Integration tests
- Security vulnerability scanning
- Code quality checks
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime
import os


class FullStackTestRunner:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.results = {}
        self.start_time = datetime.now()
        self.summary = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0
        }
        
    def run_command(self, name: str, command: list, cwd: Path = None, 
                    timeout: int = 300, critical: bool = False) -> bool:
        """Execute a command and track results"""
        if cwd is None:
            cwd = self.project_root
            
        print(f"\n{'='*70}")
        print(f"🧪 {name}")
        print(f"{'='*70}")
        print(f"Working directory: {cwd}")
        print(f"Command: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            
            # Parse test counts from output if available
            test_count = self._parse_test_count(result.stdout)
            if test_count:
                self.summary["total_tests"] += test_count.get("passed", 0)
                self.summary["total_tests"] += test_count.get("failed", 0)
                self.summary["passed"] += test_count.get("passed", 0)
                self.summary["failed"] += test_count.get("failed", 0)
            
            self.results[name] = {
                "status": "PASS" if success else "FAIL",
                "critical": critical,
                "return_code": result.returncode,
                "output_lines": len(result.stdout.split('\n')),
            }
            
            # Print results
            if success:
                print(f"✅ {name}: PASSED")
                if result.stdout:
                    lines = result.stdout.split('\n')
                    # Print last 20 lines of output
                    for line in lines[-20:]:
                        if line.strip():
                            print(f"   {line}")
            else:
                print(f"❌ {name}: FAILED")
                if result.stderr:
                    print(f"\nError output:")
                    for line in result.stderr.split('\n')[-10:]:
                        if line.strip():
                            print(f"   {line}")
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"⏱️  {name}: TIMEOUT (>{timeout}s)")
            self.results[name] = {
                "status": "TIMEOUT",
                "critical": critical
            }
            return False
        except FileNotFoundError as e:
            print(f"⚠️  {name}: SKIPPED - {str(e)}")
            self.results[name] = {
                "status": "SKIPPED",
                "critical": critical,
                "reason": str(e)
            }
            self.summary["skipped"] += 1
            return True  # Non-critical if tool not found
        except Exception as e:
            print(f"❌ {name}: ERROR - {str(e)}")
            self.results[name] = {
                "status": "ERROR",
                "critical": critical,
                "error": str(e)
            }
            self.summary["errors"] += 1
            return not critical
    
    def _parse_test_count(self, output: str) -> dict:
        """Extract test counts from pytest output"""
        counts = {"passed": 0, "failed": 0, "skipped": 0}
        
        # Look for pytest summary line
        for line in output.split('\n'):
            if "passed" in line:
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "passed" in part and i > 0:
                            counts["passed"] = int(parts[i-1])
                        if "failed" in part and i > 0:
                            counts["failed"] = int(parts[i-1])
                        if "skipped" in part and i > 0:
                            counts["skipped"] = int(parts[i-1])
                except:
                    pass
        
        return counts if any(counts.values()) else None
    
    def run_backend_tests(self) -> bool:
        """Run all backend tests"""
        print("\n" + "="*70)
        print("🔷 BACKEND TESTS")
        print("="*70)
        
        all_passed = True
        
        # Unit tests
        all_passed &= self.run_command(
            "Backend Unit Tests (API)",
            ["python", "-m", "pytest", "tests/test_api.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=True
        )
        
        # Service tests
        all_passed &= self.run_command(
            "Backend Service Tests",
            ["python", "-m", "pytest", "tests/test_services.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=False
        )
        
        # Auth tests
        all_passed &= self.run_command(
            "Backend Authentication Tests",
            ["python", "-m", "pytest", "tests/test_auth.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=True
        )
        
        # Billing tests
        all_passed &= self.run_command(
            "Backend Billing Tests",
            ["python", "-m", "pytest", "tests/test_billing.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=False
        )
        
        # Rate limiting tests
        all_passed &= self.run_command(
            "Backend Rate Limiter Tests",
            ["python", "-m", "pytest", "tests/test_rate_limiter.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=False
        )
        
        # Worker tests
        all_passed &= self.run_command(
            "Backend Worker Tests",
            ["python", "-m", "pytest", "tests/test_worker.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=False
        )
        
        return all_passed
    
    def run_security_tests(self) -> bool:
        """Run security test suite"""
        print("\n" + "="*70)
        print("🔒 SECURITY TESTS")
        print("="*70)
        
        all_passed = True
        
        # Security tests
        all_passed &= self.run_command(
            "Security Tests - All",
            ["python", "-m", "pytest", "tests/test_security.py", "-v", "--tb=short"],
            cwd=self.backend_dir,
            critical=True
        )
        
        # Security test categories
        security_categories = [
            ("Authentication", "TestAuthenticationSecurity"),
            ("Authorization", "TestAuthorizationSecurity"),
            ("Input Validation", "TestInputValidationSecurity"),
            ("Token Security", "TestTokenSecurity"),
            ("Secrets Management", "TestSecretsManagement"),
        ]
        
        for category_name, class_name in security_categories:
            all_passed &= self.run_command(
                f"Security Tests - {category_name}",
                ["python", "-m", "pytest", f"tests/test_security.py::{class_name}", "-v", "--tb=short"],
                cwd=self.backend_dir,
                critical=False
            )
        
        return all_passed
    
    def run_code_quality_checks(self) -> bool:
        """Run code quality checks"""
        print("\n" + "="*70)
        print("✨ CODE QUALITY CHECKS")
        print("="*70)
        
        all_passed = True
        
        # Type checking
        all_passed &= self.run_command(
            "Type Checking (mypy)",
            ["mypy", "app/", "--ignore-missing-imports"],
            cwd=self.backend_dir,
            critical=False
        )
        
        # Linting
        all_passed &= self.run_command(
            "Code Linting (pylint)",
            ["pylint", "app/", "--disable=R,C", "-q"],
            cwd=self.backend_dir,
            critical=False
        )
        
        # Code formatting check
        all_passed &= self.run_command(
            "Code Format Check (black)",
            ["black", "app/", "--check", "--quiet"],
            cwd=self.backend_dir,
            critical=False
        )
        
        return all_passed
    
    def run_dependency_checks(self) -> bool:
        """Check for vulnerable dependencies"""
        print("\n" + "="*70)
        print("📦 DEPENDENCY CHECKS")
        print("="*70)
        
        all_passed = True
        
        # Dependency audit
        all_passed &= self.run_command(
            "Dependency Vulnerability Scan (pip-audit)",
            ["pip-audit"],
            cwd=self.backend_dir,
            critical=False
        )
        
        return all_passed
    
    def run_frontend_checks(self) -> bool:
        """Run frontend tests and checks"""
        print("\n" + "="*70)
        print("⚛️  FRONTEND CHECKS")
        print("="*70)
        
        all_passed = True
        
        # Type checking
        all_passed &= self.run_command(
            "Frontend Type Checking (TypeScript)",
            ["npm", "run", "type-check"],
            cwd=self.frontend_dir,
            critical=False
        )
        
        # Linting
        all_passed &= self.run_command(
            "Frontend Linting (ESLint)",
            ["npm", "run", "lint", "--", "--quiet"],
            cwd=self.frontend_dir,
            critical=False
        )
        
        return all_passed
    
    def run_integration_tests(self) -> bool:
        """Run integration tests"""
        print("\n" + "="*70)
        print("🔗 INTEGRATION TESTS")
        print("="*70)
        
        all_passed = True
        
        # Full test suite
        all_passed &= self.run_command(
            "Full Backend Test Suite",
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "-x"],
            cwd=self.backend_dir,
            critical=True
        )
        
        return all_passed
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*70)
        print("📊 TEST SUMMARY REPORT")
        print("="*70)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Print summary
        print(f"\nElapsed Time: {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
        print(f"Tests Executed: {self.summary['total_tests']}")
        print(f"Passed: {self.summary['passed']} ✅")
        print(f"Failed: {self.summary['failed']} ❌")
        print(f"Skipped: {self.summary['skipped']} ⏭️")
        print(f"Errors: {self.summary['errors']} ⚠️")
        
        # Detailed results
        print(f"\nDetailed Results:")
        print(f"{'Test Name':<50} {'Status':<10} {'Critical':<10}")
        print("-" * 70)
        
        for test_name, test_result in self.results.items():
            status = test_result["status"]
            critical = "YES" if test_result.get("critical") else "no"
            status_icon = {
                "PASS": "✅",
                "FAIL": "❌",
                "SKIPPED": "⏭️",
                "ERROR": "⚠️",
                "TIMEOUT": "⏱️"
            }.get(status, "❓")
            
            print(f"{test_name:<50} {status_icon} {status:<8} {critical:<10}")
        
        # Save JSON report
        report = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "summary": self.summary,
            "results": self.results
        }
        
        report_file = self.project_root / "fullstack-test-report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 Full report saved to: {report_file}")
        
        # Overall status
        print(f"\n{'='*70}")
        critical_failures = sum(1 for r in self.results.values() 
                               if r["status"] not in ["PASS", "SKIPPED"] and r.get("critical"))
        
        if critical_failures > 0:
            print(f"🚨 {critical_failures} CRITICAL TEST FAILURE(S) DETECTED")
            return False
        elif self.summary["failed"] > 0:
            print(f"⚠️  {self.summary['failed']} non-critical test(s) failed")
            return True
        else:
            print(f"✅ ALL TESTS PASSED!")
            return True
    
    def run_all(self):
        """Run complete full-stack test suite"""
        print("="*70)
        print("🚀 FULL-STACK TEST SUITE")
        print("="*70)
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Project root: {self.project_root}")
        
        all_passed = True
        
        # Run test suites
        all_passed &= self.run_backend_tests()
        all_passed &= self.run_security_tests()
        all_passed &= self.run_code_quality_checks()
        all_passed &= self.run_dependency_checks()
        
        # Frontend checks (optional - may not be set up)
        # all_passed &= self.run_frontend_checks()
        
        # Integration tests
        # all_passed &= self.run_integration_tests()
        
        # Generate report
        report_success = self.generate_report()
        
        return all_passed and report_success


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Full-Stack Test Suite Runner")
    parser.add_argument("--backend-only", action="store_true", help="Run only backend tests")
    parser.add_argument("--security-only", action="store_true", help="Run only security tests")
    parser.add_argument("--quality-only", action="store_true", help="Run only code quality checks")
    parser.add_argument("--report", action="store_true", help="Generate report only")
    
    args = parser.parse_args()
    
    runner = FullStackTestRunner()
    
    if args.backend_only:
        success = runner.run_backend_tests()
    elif args.security_only:
        success = runner.run_security_tests()
    elif args.quality_only:
        success = runner.run_code_quality_checks()
    elif args.report:
        runner.generate_report()
        return 0
    else:
        success = runner.run_all()
    
    runner.generate_report()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
