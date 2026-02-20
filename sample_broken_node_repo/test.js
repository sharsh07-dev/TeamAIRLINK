const { add, subtract } = require('./index');

let passes = 0;
let fails = 0;

console.log("Running suite: Math Ops");

// Test 1: Add
if (add(1, 2) === 3) {
    passes++;
} else {
    console.error("FAIL: add(1,2) -> Expected 3");
    fails++;
}

// Test 2: Subtract
if (subtract(5, 2) === 3) {
    passes++;
} else {
    console.error("FAIL: subtract(5,2) -> Expected 3, got", subtract(5, 2));
    fails++;
}

console.log(`${passes} passing  ${fails} failing`);  // Matches TestRunner regex
if (fails > 0) process.exit(1);
