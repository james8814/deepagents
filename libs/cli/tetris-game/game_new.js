// Phaser game configuration
const config = {
    type: Phaser.AUTO,
    width: 300,
    height: 600,
    scene: {
        preload: preload,
        create: create,
        update: update
    }
};

// Create the game instance
const game = new Phaser.Game(config);

function preload() {
    // Load assets here
}

function create() {
    // Define the shapes of the tetrominoes
    const TETROMINOES = [
        [  [0, 0, 0],
           [1, 1, 1],
           [0, 1, 0]], // T
        [  [0, 1, 0],
           [1, 1, 1],
           [0, 0, 0]], // I
        [  [1, 1, 0],
           [0, 1, 1],
           [0, 0, 0]], // S
        [  [0, 1, 1],
           [1, 1, 0],
           [0, 0, 0]], // Z
        [  [1, 1],
           [1, 1]], // O
        [  [0, 1, 0],
           [1, 1, 1],
           [0, 0, 0]], // L
        [  [1, 0, 0],
           [1, 1, 1],
           [0, 0, 0]]  // J
    ];

    // Variables to store the current tetromino and its position
    let currentTetromino = null;
    let currentPosition = { x: 0, y: 0 };

    // Function to generate a random tetromino
    function generateTetromino() {
        const shapeIndex = Math.floor(Math.random() * TETROMINOES.length);
        currentTetromino = TETROMINOES[shapeIndex];
        currentPosition = { x: Math.floor(config.width / 2) - 1, y: 0 };
    }

    // Call the generateTetromino function to create the first tetromino
    generateTetromino();

    // Function to draw the current tetromino
    function drawTetromino() {
        for (let y = 0; y < currentTetromino.length; y++) {
            for (let x = 0; x < currentTetromino[y].length; x++) {
                if (currentTetromino[y][x] === 1) {
                    // Draw the block at the current position
                    this.add.rectangle(currentPosition.x + x * 20, currentPosition.y + y * 20, 20, 20, 0xff0000);
                }
            }
        }
    }

    // Bind the drawTetromino function to the correct context
    this.drawTetromino = drawTetromino.bind(this);

    // Initial draw
    this.drawTetromino();
}

function update() {
    // Update game logic here
}
