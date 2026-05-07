/*
Bug: JavaScript async race condition
Description: Race condition in parallel async calls where order matters
Expected behavior: Data should be processed in sequence but parallel calls cause inconsistent results
*/

class DataProcessor {
    constructor() {
        this.results = [];
        this.processing = false;
    }

    async processData(dataArray) {
        if (this.processing) {
            throw new Error("Already processing data");
        }
        
        this.processing = true;
        this.results = [];
        
        // BUG: Race condition - starting multiple async operations
        // without proper coordination, expecting sequential processing
        const promises = dataArray.map(async (data, index) => {
            // Simulate async processing with variable delay
            await this.simulateAsyncWork(Math.random() * 100);
            
            // This should be processed in order but parallel execution
            // causes race conditions in the results array
            this.results[index] = `Processed: ${data} at ${Date.now()}`;
        });
        
        // Wait for all to complete but order is not guaranteed
        await Promise.all(promises);
        this.processing = false;
        
        return this.results;
    }

    simulateAsyncWork(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

async function main() {
    const processor = new DataProcessor();
    const testData = ['A', 'B', 'C', 'D', 'E'];
    
    console.log("Testing race condition with async operations:");
    
    for (let i = 0; i < 5; i++) {
        console.log(`\nRun ${i + 1}:`);
        try {
            const results = await processor.processData(testData);
            console.log("Results:", results);
            
            // Check if results are in expected order
            const expectedOrder = testData.map(data => `Processed: ${data}`);
            const isInOrder = results.every((result, index) => 
                result.startsWith(`Processed: ${testData[index]}`)
            );
            
            console.log("Order correct:", isInOrder);
        } catch (error) {
            console.error("Error:", error.message);
        }
    }
}

main().catch(console.error);

// TODO: enviar para o pipeline com: python main.py "JavaScript race condition in async data processing - parallel calls causing order issues"
