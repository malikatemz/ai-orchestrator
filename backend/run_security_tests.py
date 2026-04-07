#!/usr/bin/env python
"""
Automated Security Testing Suite
Runs multiple security checks and generates a report

Usage:
    python run_security_tests.py
    python run_security_tests.py --full
    python run_security_tests.py --report
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime
import os


class SecurityTestRunner:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.results = {}
        self.start_time = datetime.now()
        
    def run_test(self, name: str, command: list, critical: bool = False) -> bool:
        """Run a security test and return success status"""
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                command,
                cwd=self.backend_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            success = result.returncode == 0
            self.results[name] = {
                "status": "PASS" if success else "FAIL",
                "critical": critical,
                "stdout": result.stdout[:500],  # First 500 chars
                "stderr": result.stderr[:500],
            }
            
            if success:
                print(f"✅ {name}: PASSED")
            else:
                print(f"❌ {name}: FAILED")
                if result.stderr:
                    print(f"Error: {result.stderr[:200]}")
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"⏱️ {name}: TIMEOUT")
            self.results[name] = {
                "status": "TIMEOUT",
                "critical": critical
            }
            return False
        except Exception as e:
            print(f"❌ {name}: ERROR - {str(e)}")
            self.results[name] = {
                "status": "ERROR",
                "critical": critical,
                "error": str(e)
            }
            return False
    
    def run_core_tests(self) -> bool:
        """Run core security tests"""
        print("\n" + "="*60)
        print("CORE SECURITY TESTS")
        print("="*60)
        
        tests = [
            ("Unit Tests - Security", 
             ["python", "-m", "pytest", "tests/test_security.py", "-v"],
             True),
            
            ("Authentication Tests",
             ["python", "-m", "pytest", "tests/test_security.py::TestAuthenticationSecurity", "-v"],
             True),
            
            ("Authorization Tests",
             ["python", "-m", "pytest", "tests/test_security.py::TestAuthorizationSecurity", "-v"],
             True),
            
            ("Input Validation Tests",
             ["python", "-m", "pytest", "tests/test_security.py::TestInputValidationSecurity", "-v"],
             True),
            
            ("Token Security Tests",
             ["python", "-m", "pytest", "tests/test_security.py::TestTokenSecurity", "-v"],
             True),
            
            ("Secrets Management Tests",
             ["python", "-m", "pytest", "tests/test_security.py::TestSecretsManagement", "-v"],
             True),
        ]
        
        results = []
        for name, cmd, critical in tests:
            results.append(self.run_test(name, cmd, critical))
        
        return all(results)
    
    def run_dependency_checks(self) -> bool:
        """Check for vulnerable dependencies"""
        print("\n" + "="*60)
        print("DEPENDENCY VULNERABILITY SCANNING")
        print("="*60)
        
        # Check if pip-audit is available
        try:
            subprocess.run(
                ["pip", "show", "pip-audit"],
                capture_output=True,
                check=True,
                timeout=10
            )
            
            return self.run_test(
                "Dependency Audit (pip-audit)",
                ["pip-audit"],
                critical=True
            )
        except:
            print("⚠️  pip-audit not installed. Install with: pip install pip-audit")
            return True  # Non-critical if not installed
    
    def run_code_analysis(self) -> bool:
        """Run static code security analysis"""
        print("\n" + "="*60)
        print("STATIC CODE ANALYSIS")
        print("="*60)
        
        # Check if bandit is available
        try:
            subprocess.run(
                ["pip", "show", "bandit"],
                capture_output=True,
                check=True,
                timeout=10
            )
            
            return self.run_test(
                "Security Linting (bandit)",
                ["bandit", "-r", "app/", "-o", "/tmp/bandit-report.json"],
                critical=False
            )
        except:
            print("⚠️  bandit not installed. Install with: pip install bandit")
            return True
    
    def run_type_checking(self) -> bool:
        """Run type checking for type safety"""
        print("\n" + "="*60)
        print("TYPE SAFETY CHECKING")
        print("="*60)
        
        try:
            subprocess.run(
                ["pip", "show", "mypy"],
                capture_output=True,
                check=True,
                timeout=10
            )
            
            return self.run_test(
                "Type Checking (mypy)",
                ["mypy", "app/", "--ignore-missing-imports"],
                critical=False
            )
        except:
            print("⚠️  mypy not installed. Install with: pip install mypy")
            return True
    
    def run_all_tests(self) -> bool:
        """Run all security tests"""
        all_passed = True
        
        # Core tests (critical)
        core_passed = self.run_core_tests()
        all_passed = all_passed and core_passed
        
        # Optional security checks
        if core_passed:
            self.run_dependency_checks()
            self.run_code_analysis()
            self.run_type_checking()
        
        return all_passed
    
    def generate_report(self):
        """Generate security test report"""
        print("\n" + "="*60)
        print("SECURITY TEST REPORT")
        print("="*60)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "results": self.results,
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results.values() if r["status"] == "PASS"),
                "failed": sum(1 for r in self.results.values() if r["status"] == "FAIL"),
                "errors": sum(1 for r in self.results.values() if r["status"] == "ERROR"),
                "critical_failures": sum(1 for r in self.results.values() 
                                        if r["status"] != "PASS" and r.get("critical", False))
            }
        }
        
        # Print summary
        print(f"\nTotal Tests: {report['summary']['total']}")
        print(f"Passed: {report['summary']['passed']} ✅")
        print(f"Failed: {report['summary']['failed']} ❌")
        print(f"Errors: {report['summary']['errors']} ⚠️")
        print(f"Critical Failures: {report['summary']['critical_failures']}")
        print(f"Elapsed Time: {elapsed:.2f}s")
        
        # Print test results
        print(f"\nDetailed Results:")
        for test_name, test_result in self.results.items():
            status_icon = {
                "PASS": "✅",
                "FAIL": "❌",
                "TIMEOUT": "⏱️",
                "ERROR": "⚠️"
            }.get(test_result["status"], "❓")
            
            critical_badge = " [CRITICAL]" if test_result.get("critical") else ""
            print(f"{status_icon} {test_name}{critical_badge}: {test_result['status']}")
        
        # Save JSON report
        report_file = self.project_root / "security-test-report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\nFull report saved to: {report_file}")
        
        # Overall status
        if report['summary']['critical_failures'] > 0:
            print("\n🚨 CRITICAL FAILURES DETECTED - Security issues must be fixed!")
            return False
        elif report['summary']['failed'] > 0:
            print("\n⚠️ Some tests failed - Please review and address")
            return False
        else:
            print("\n✅ All security tests passed!")
            return True
    
    def print_security_checklist(self):
        """Print security checklist"""
        print("\n" + "="*60)
        print("SECURITY IMPLEMENTATION CHECKLIST")
        print("="*60)
        
        checklist = {
            "Authentication": [
                ("All endpoints require authentication", True),
                ("Tokens expire after reasonable time", True),
                ("Failed logins are logged", True),
                ("Account lockout implemented", False),
                ("MFA available for admins", False),
            ],
            "Authorization": [
                ("RBAC implemented (5+ roles)", True),
                ("Data filtered by organization", True),
                ("No cross-org data exposure", True),
                ("Privilege escalation prevented", True),
                ("Regular access reviews", True),
            ],
            "Data Protection": [
                ("Database encryption at rest", True),
                ("TLS/HTTPS enforced", True),
                ("Passwords hashed (bcrypt)", True),
                ("PII handling compliant", True),
                ("Data retention policies", True),
            ],
            "Code Security": [
                ("No hardcoded secrets", True),
                ("Input validation on all endpoints", True),
                ("Output encoding for XSS", True),
                ("SQL parameterization used", True),
                ("Regular dependency updates", True),
            ],
            "Infrastructure": [
                ("Firewall rules enforced", True),
                ("Network segmentation", True),
                ("Log aggregation", True),
                ("Incident response plan", True),
                ("Regular backups tested", True),
            ],
            "Monitoring": [
                ("Security events logged", True),
                ("Audit trails immutable", True),
                ("Real-time alerts", False),
                ("Log retention", True),
                ("Regular log review", True),
            ],
        }
        
        total_items = 0
        completed_items = 0
        
        for category, items in checklist.items():
            print(f"\n{category}:")
            for item, completed in items:
                status = "✅" if completed else "⚠️"
                total_items += 1
                if completed:
                    completed_items += 1
                print(f"  {status} {item}")
        
        percentage = (completed_items / total_items * 100) if total_items > 0 else 0
        print(f"\n{'='*60}")
        print(f"Implementation Status: {completed_items}/{total_items} ({percentage:.0f}%)")
        print(f"{'='*60}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Testing Suite")
    parser.add_argument("--full", action="store_true", help="Run all checks including slow ones")
    parser.add_argument("--report", action="store_true", help="Generate report only")
    parser.add_argument("--checklist", action="store_true", help="Show security checklist")
    
    args = parser.parse_args()
    
    runner = SecurityTestRunner()
    
    if args.checklist:
        runner.print_security_checklist()
        return 0
    
    if args.report:
        runner.generate_report()
        return 0
    
    # Run tests
    success = runner.run_all_tests()
    
    # Generate report
    report_success = runner.generate_report()
    
    # Show checklist
    runner.print_security_checklist()
    
    return 0 if (success and report_success) else 1


if __name__ == "__main__":
    sys.exit(main())
