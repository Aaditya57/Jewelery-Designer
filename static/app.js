angular.module('jewelryApp', [])
.filter('capitalizeFirst', function() {
    return function(input) {
        if (!input) return '';
        return input.charAt(0).toUpperCase() + input.slice(1).toLowerCase();
    };
})
.controller('JewelryController', ['$http', function($http) {
    var vm = this; // ViewModel pattern
    vm.design = {
        jewelry_type: 'ring',
        metal_type: 'yellow gold',
        stone_type: 'diamond',
        gender: 'women', // Default
        description: '',
        numImages: 1, // Default number of images
        model: '5c232a9e-9061-4777-980a-ddc8e65647c6', // Default model
        enhancePrompt: false, // NEW: Default to true (checked)
        challenge: '', // NEW: Field for challenge passphrase
        product_style: '', // NEW: Field for product style
        setting_type: '' // NEW: Field for setting type
    };
    vm.images = []; // Images from current generation
    vm.isLoading = false;
    vm.errorMessage = '';
    vm.savedDesigns = []; // NEW: Array to hold previously saved designs

    vm.isCommentsMode = false; // NEW: Track input mode

    vm.toggleInputMode = function() {
        vm.isCommentsMode = !vm.isCommentsMode;

        // Clear the values of the inactive mode
        if (vm.isCommentsMode) {
            vm.design.product_style = '';
            vm.design.setting_type = '';
        } else {
            vm.design.description = '';
        }
    };

    // --- NEW: Increment/Decrement functions for the counter ---
    vm.incrementImages = function() {
        if (vm.design.numImages < 8) { // Maximum number of images
            vm.design.numImages++;
        }
    };

    vm.decrementImages = function() {
        if (vm.design.numImages > 1) { // Minimum number of images
            vm.design.numImages--;
        }
    };
    // --- END NEW FUNCTIONS ---
    vm.generateImagesDesgin = function() {
        jewelry_type = ''
        metal_type = ''
        stone_type = ''
        gender = ''
        vm.generateImages()
    }

    vm.generateImages = function() {
        vm.isLoading = true;
        vm.errorMessage = '';
        vm.images = []; // Clear previous images

        // Basic validation (optional, can be more robust)
        if (!vm.design.jewelry_type || (!vm.isCommentsMode && (!vm.design.product_style || !vm.design.setting_type)) || (vm.isCommentsMode && !vm.design.description)) {
            vm.errorMessage = "Please select or provide input for the design.";
            vm.isLoading = false;
            return;
        }

        // Send the model ID and numImages along with other design parameters
        $http.post('/generate-jewelry', vm.design)
            .then(function(response) {
                vm.isLoading = false;
                if (response.data && response.data.images) {
                    vm.images = response.data.images;
                    vm.fetchSavedDesigns(); // NEW: Refresh saved designs after a new generation
                } else {
                    vm.errorMessage = "No images returned. Please try again.";
                }
            })
            .catch(function(error) {
                vm.isLoading = false;
                console.error("Error generating images:", error);
                vm.errorMessage = "Failed to generate images. " + (error.data && error.data.error ? error.data.error : "Server error.");
            });
    };

    // --- NEW: Function to fetch saved designs ---
    vm.fetchSavedDesigns = function() {
        $http.get('/get-saved-designs')
            .then(function(response) {
                vm.savedDesigns = response.data;
                console.log("Fetched saved designs:", vm.savedDesigns);
            })
            .catch(function(error) {
                console.error("Error fetching saved designs:", error);
                // Optionally set an error message for the user
            });
    };

    // Initial fetch of saved designs when the page loads
    vm.fetchSavedDesigns();

    vm.dynamicOptions = {
        ring: [
            'Alternate Bands', 'Bypass', 'Channel Set', 'Chevron', 'Colored Diamond', 'Criss Cross',
            'Curb & Cuban', 'Curved', 'Double halo', 'Eternity', 'Fancy', 'Floral', 'Gemstone Accent',
            'Halo', 'Solitaire', 'Paper Clip', 'Plain Shank', 'Signature Band', 'Split Shank',
            'Twisted Shank', 'Stackable', 'Straight', 'Tapered Shank', 'Wide'
        ],
        earring: [
            'Hoop', 'Chain', 'Curb & Cuban', 'Dangling', 'Drop', 'Fancy', 'Fish Hook', 'Floral',
            'Halo', 'C-Hoop', 'J-Hoop', 'Jacket', 'Paper Clip', 'Shoulder Duster', 'Teardrop', 'Threader'
        ],
        pendant: [
            'Chain', 'Curb & Cuban', 'Fancy', 'Floral', 'Halo', 'Locket', 'Multi Layered',
            'Paper Clip', 'Teardrop', 'Religious', 'Alphabets', 'Charm', 'Solitaire'
        ],
        bracelet: [
            'Chain', 'Curb & Cuban', 'Floral', 'Gemstone Accent', 'Halo', 'Lariat', 'Link',
            'Paper Clip', 'Tennis', 'Mixed Stones', 'Bangle', 'Cuff'
        ],
        necklace: [
            'Station', 'Lariat', 'Y-Necklace', 'Chokar', 'Bib Necklace', 'Collar Necklace',
            'Tennis Necklace', 'Torque Necklace', 'Bar Necklace', 'Multi Strand Necklace', 'Nameplate Necklace'
        ]
    };

    vm.design.dynamicOption = '';

    // --- END NEW: Function to fetch saved designs ---
}]);