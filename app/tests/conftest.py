import pytest

# The CLAUDE.md section 18 example test case, shared across detection,
# anonymization, and restore tests.
SAMPLE_PYTHON_SOURCE = (
    "import requests\n"
    "\n"
    "class PaymentGatewayClient:\n"
    "    def establish_connection(self, UserName, Password):\n"
    '        url = "https://prod.payment.mycompany.internal/api"\n'
    '        token = "ghp_1234567890abcdef1234567890abcdef1234"\n'
    "        return requests.post(url, auth=(UserName, Password))\n"
)


@pytest.fixture
def sample_python_source() -> str:
    return SAMPLE_PYTHON_SOURCE
