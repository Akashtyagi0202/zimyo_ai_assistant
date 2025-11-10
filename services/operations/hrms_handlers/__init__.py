"""
HRMS Operation Handlers

Individual handlers for different HRMS operations.
Each handler is responsible for a specific operation type.

Handlers:
- leave_balance: Query leave balance
- attendance: Mark attendance (check-in/check-out)
- apply_leave: Apply for leave
- apply_regularization: Apply for attendance regularization
- apply_onduty: Apply for on-duty (WFH, client site, field work)
- get_holidays: Get upcoming company holidays
- get_salary_slip: Get and download salary slip
- [Future] calendar: Book calendar with manager
"""

from .leave_balance import handle_leave_balance
from .attendance import handle_attendance
from .apply_leave import handle_apply_leave
from .apply_regularization import handle_apply_regularization
from .apply_onduty import handle_apply_onduty
from .get_holidays import handle_get_holidays
from .get_salary_slip import handle_get_salary_slip

__all__ = [
    'handle_leave_balance',
    'handle_attendance',
    'handle_apply_leave',
    'handle_apply_regularization',
    'handle_apply_onduty',
    'handle_get_holidays',
    'handle_get_salary_slip',
]
