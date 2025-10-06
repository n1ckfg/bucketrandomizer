"use strict";

class CookieManager {

    static getNumbers(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) {
                const value = c.substring(nameEQ.length, c.length);
                return value.split(',').map(Number);
            }
        }
        return [];
    }

    static setNumbers(name, numbers) {
        const value = numbers.join(',');
        const date = new Date();
        date.setTime(date.getTime() + (365*24*60*60*1000)); // Expiration time for the cookie 
        const expires = "expires=" + date.toUTCString();
        document.cookie = name + "=" + value + ";" + expires + ";path=/";
    }

    static clear(name) {
        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/";
    }

}

function getUniqueRandomNumber(cookieName, maxRange) {
	//const maxRange = 31;

    let usedNumbers = CookieManager.getNumbers(cookieName);
    
    // Find a unique number
    while (true) {
        const randomNumber = Math.floor(Math.random() * maxRange);

        // Check if used
        if (!usedNumbers.includes(randomNumber)) {
            usedNumbers.push(randomNumber);
            CookieManager.setNumbers(cookieName, usedNumbers);
            console.log(`Generated a new unique number: ${randomNumber}. Total used: ${usedNumbers.length}. Remaining: ${maxRange - usedNumbers.length}`);
            return randomNumber;
        }

        // Check if the range is exhausted
        if (usedNumbers.length >= maxRange) {
            CookieManager.clear(cookieName);
            console.warn("All numbers from 0-" + (maxRange - 1) + " have been used. The cookie has been cleared.");
            
            usedNumbers = []; // The next iteration will find a new number.
        }
    }
}

// ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

document.addEventListener("DOMContentLoaded", () => {
    const url = "sample.json"; 

    async function loadJson(url) {
        try {
            const response = await fetch(url);

            if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

            const data = await response.json();

            const uniqueNumber = getUniqueRandomNumber("myUniqueNumbers", data.length);

            console.log(`Unique index number: ${uniqueNumber}`);

            const text = data[uniqueNumber].body;

			//document.body.appendChild(newTextNode);

			const textBox = document.getElementById("textbox");
            const textNode = document.createTextNode(text);
			textBox.appendChild(textNode);
        } catch (error) {
            console.log(`Error loading JSON: ${error.message}.`);
        }
    }

    loadJson(url);
});