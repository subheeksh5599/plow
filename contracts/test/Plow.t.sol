// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {MockSkySavings} from "../src/MockSkySavings.sol";

contract PlowTest is Test {
    MockUSDC usdc;
    MockSkySavings sky;
    address alice = makeAddr("alice");

    function setUp() public {
        usdc = new MockUSDC();
        sky = new MockSkySavings(address(usdc));
    }

    function test_MockUSDC_MintAndTransfer() public {
        usdc.mint(alice, 1_000_000e6); // 1,000,000 USDC
        assertEq(usdc.balanceOf(alice), 1_000_000e6);
        vm.prank(alice);
        usdc.transfer(address(this), 500e6);
        assertEq(usdc.balanceOf(address(this)), 500e6);
    }

    function test_Deposit_MintsSharesOneToOne() public {
        usdc.mint(alice, 10_000e6);
        vm.startPrank(alice);
        usdc.approve(address(sky), 10_000e6);
        uint256 shares = sky.deposit(1_000e6);
        vm.stopPrank();
        assertEq(shares, 1_000e6 * 1e12);
        assertEq(sky.balanceOf(alice), 1_000e6 * 1e12);
        assertEq(usdc.balanceOf(address(sky)), 1_000e6);
    }

    function test_Deposit_ZeroReverts() public {
        vm.expectRevert(bytes("Sky: zero"));
        sky.deposit(0);
    }

    function test_Deposit_InsufficientAllowanceReverts() public {
        usdc.mint(alice, 10e6);
        vm.prank(alice);
        vm.expectRevert(bytes("USDC: allowance"));
        sky.deposit(10e6);
    }

    function test_Withdraw_ReturnsUnderlying() public {
        usdc.mint(alice, 10_000e6);
        vm.startPrank(alice);
        usdc.approve(address(sky), 10_000e6);
        uint256 shares = sky.deposit(2_000e6);
        uint256 amount = sky.withdraw(shares);
        vm.stopPrank();
        assertEq(amount, 2_000e6);
        assertEq(sky.balanceOf(alice), 0);
        assertEq(usdc.balanceOf(alice), 10_000e6);
    }

    function test_Withdraw_InsufficientSharesReverts() public {
        vm.expectRevert(bytes("Sky: balance"));
        sky.withdraw(1e18);
    }

    function test_SetRate_OnlyOwner() public {
        sky.setRate(512); // 5.12%
        assertEq(sky.rateBps(), 512);
        vm.prank(alice);
        vm.expectRevert(bytes("Sky: not owner"));
        sky.setRate(100);
    }
}
