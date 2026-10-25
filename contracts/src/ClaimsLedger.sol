// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Audit-only ledger for a synthetic insurance demo. It never holds or sends funds.
contract ClaimsLedger {
    enum State { None, Submitted, UnderReview, Approved, Rejected, SettledSimulated }
    bytes32 public constant RELAYER = keccak256("RELAYER");
    bytes32 public constant REVIEWER = keccak256("REVIEWER");
    bytes32 public constant OPERATOR = keccak256("OPERATOR");
    address public admin;
    bool public paused;
    mapping(bytes32 => mapping(address => bool)) public roles;

    struct Claim {
        State state;
        bytes32 evidenceCommitment;
        bytes32 decisionCommitment;
        bytes32 receiptCommitment;
        uint256 approvedMinor;
    }
    mapping(bytes32 => Claim) private claims;

    event RoleChanged(bytes32 indexed role, address indexed account, bool enabled);
    event PauseChanged(bool paused);
    event ClaimSubmitted(bytes32 indexed id, bytes32 evidenceCommitment);
    event ReviewStarted(bytes32 indexed id);
    event ClaimDecided(bytes32 indexed id, bool approved, uint256 approvedMinor, bytes32 decisionCommitment);
    event SettlementSimulated(bytes32 indexed id, bytes32 receiptCommitment);

    error Unauthorized();
    error WrongState();
    error InvalidInput();
    error Paused();

    constructor() { admin = msg.sender; }

    modifier onlyAdmin() { if (msg.sender != admin) revert Unauthorized(); _; }
    modifier onlyRole(bytes32 role) { if (!roles[role][msg.sender]) revert Unauthorized(); _; }
    modifier whenActive() { if (paused) revert Paused(); _; }

    function setRole(bytes32 role, address account, bool enabled) external onlyAdmin {
        if (account == address(0) || (role != RELAYER && role != REVIEWER && role != OPERATOR)) revert InvalidInput();
        roles[role][account] = enabled;
        emit RoleChanged(role, account, enabled);
    }

    function setPaused(bool value) external onlyAdmin { paused = value; emit PauseChanged(value); }

    function transferAdmin(address next) external onlyAdmin {
        if (next == address(0)) revert InvalidInput();
        admin = next;
    }

    function submitClaim(bytes32 id, bytes32 evidenceCommitment) external onlyRole(RELAYER) whenActive {
        if (id == bytes32(0) || evidenceCommitment == bytes32(0)) revert InvalidInput();
        if (claims[id].state != State.None) revert WrongState();
        claims[id].state = State.Submitted;
        claims[id].evidenceCommitment = evidenceCommitment;
        emit ClaimSubmitted(id, evidenceCommitment);
    }

    function startReview(bytes32 id) external onlyRole(REVIEWER) whenActive {
        if (claims[id].state != State.Submitted) revert WrongState();
        claims[id].state = State.UnderReview;
        emit ReviewStarted(id);
    }

    function decideClaim(bytes32 id, bool approve, uint256 approvedMinor, bytes32 decisionCommitment) external onlyRole(REVIEWER) whenActive {
        if (claims[id].state != State.UnderReview) revert WrongState();
        if (decisionCommitment == bytes32(0) || (approve && approvedMinor == 0) || (!approve && approvedMinor != 0)) revert InvalidInput();
        Claim storage claim = claims[id];
        claim.state = approve ? State.Approved : State.Rejected;
        claim.approvedMinor = approvedMinor;
        claim.decisionCommitment = decisionCommitment;
        emit ClaimDecided(id, approve, approvedMinor, decisionCommitment);
    }

    function recordSimulatedSettlement(bytes32 id, bytes32 receiptCommitment) external onlyRole(OPERATOR) whenActive {
        if (claims[id].state != State.Approved) revert WrongState();
        if (receiptCommitment == bytes32(0)) revert InvalidInput();
        claims[id].state = State.SettledSimulated;
        claims[id].receiptCommitment = receiptCommitment;
        emit SettlementSimulated(id, receiptCommitment);
    }

    function getClaim(bytes32 id) external view returns (Claim memory) { return claims[id]; }
}
