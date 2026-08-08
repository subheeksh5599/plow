// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {MockUSDC} from "./MockUSDC.sol";

/// @notice Mock Sky-Savings-style venue: deposit USDC (6-dec), receive sUSDS
///         shares (18-dec) 1:1. rateBps is display-only (annualized, bps).
contract MockSkySavings {
    string public constant name = "Mock Sky Savings";
    string public constant symbol = "sUSDS";
    uint8 public constant decimals = 18;

    MockUSDC public immutable underlying;
    address public owner;
    uint256 public rateBps;

    uint256 public totalShares;
    mapping(address => uint256) public balanceOf;

    event Deposit(address indexed user, uint256 amount, uint256 shares);
    event Withdraw(address indexed user, uint256 shares, uint256 amount);
    event RateSet(uint256 rateBps);

    constructor(address _underlying) {
        underlying = MockUSDC(_underlying);
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Sky: not owner");
        _;
    }

    function setRate(uint256 _rateBps) external onlyOwner {
        rateBps = _rateBps;
        emit RateSet(_rateBps);
    }

    /// @notice 1:1 deposit: pulls USDC, mints 18-dec shares.
    function deposit(uint256 amount) external returns (uint256 shares) {
        require(amount > 0, "Sky: zero");
        underlying.transferFrom(msg.sender, address(this), amount);
        shares = amount * 1e12;
        balanceOf[msg.sender] += shares;
        totalShares += shares;
        emit Deposit(msg.sender, amount, shares);
    }

    /// @notice Burn shares, return USDC 1:1.
    function withdraw(uint256 shares) external returns (uint256 amount) {
        require(balanceOf[msg.sender] >= shares, "Sky: balance");
        balanceOf[msg.sender] -= shares;
        totalShares -= shares;
        amount = shares / 1e12;
        underlying.transfer(msg.sender, amount);
        emit Withdraw(msg.sender, shares, amount);
    }
}
