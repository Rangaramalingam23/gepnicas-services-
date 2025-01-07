<template>
  <div class="overflow-auto total">
    <div class="pgtitle" style="padding-left: 4em;">
      <h4 class="title">{{ this.title }}</h4>
      <b-pagination 
        v-model="currentPage"
        :total-rows="totalRows"
        :per-page="perPage"
        aria-controls="my-table"
        first-number
        last-number
        @input="currentPageChanged"
      ></b-pagination>
    </div>

    <div id="search_c" style="padding-left: 4em;">
      <input type="text" placeholder="Search" v-model="search_text">
      <br>
    </div>
    <br>

    <div id="rad" style="padding-left: 4em;">
      <div id="radiobutton" class="radio-group">
        <div>
          <input type="radio" v-model="selectedOption" value="bids">
          <label>Bids</label>
        </div>
        <div>
          <input type="radio" v-model="selectedOption" value="tender">
          <label>Tenders</label>
        </div>
      </div>
    </div>

    <!-- Sync button, appears only on Sync Pending page -->
    <!-- <div v-if="title === 'Sync Pending'" class="sync-container" style="padding-left: 64em; margin-bottom: 10px;">
      <button @click="syncAllSelected" class="btn btn-sm btn-outline-primary">
        Sync Selected Rows
      </button>
    </div> -->

    <!-- Table -->
    <b-table
      id="my-table"
      :items="filteredItems"
      :fields="fieldsWithCheckbox"
      :per-page="perPage"
      :current-page="currentPage"
      bordered
      small
    >
      <!-- Header for Select All Column (checkbox and sync) -->
      <template #head(checkbox)="data">
      <span v-if="showCheckBoxSync" class="select-all-label">Select All</span>
      <input 
      type="checkbox" 
      v-model="selectAll"
      @change="toggleSelectAll"
      v-if="showCheckBoxSync"
      class="select-all-checkbox"
      />
     </template>


      <!-- Header for Sync/Meta Data/Soft Link Column -->
      <template #head(sync)="data">
        <span v-if="title === 'Sync Pending'">Sync All</span>
        <img
          v-if="title === 'Sync Pending'"
          :src="syncIcon"
          alt="Sync All"
          class="sync-icon-header"
         
        />

        <span v-if="title === 'Meta Data Pending'">Create Meta Data</span>
        <img
          v-if="title === 'Meta Data Pending'"
          :src="linkIcon"
          alt="Create Meta Data"
          class="sync-icon-header"
          @click="handleMetaDataClick"
        />

        <span v-if="title === 'Soft Link Pending'">Create Soft Link</span>
        <img
          v-if="title === 'Soft Link Pending'"
          :src="processIcon"
          alt="Create Soft Link"
          class="sync-icon-header"
          @click="handleSoftLinkClick"
        />
      </template>

      <!-- Checkbox and Sync Button for Rows -->
      <template #cell(checkbox)="data">
        <input
          type="checkbox"
          v-model="selectedRows"
          :value="data.item"
          @change="updateSelectAll"
          v-if="showCheckBoxSync"
        />
      </template>

      <template #cell(sync)="data">
        <img
          v-if="title === 'Sync Pending'"
          :src="syncIcon"
          alt="Sync Row"
          class="sync-icon-row"
          @click="handleSync"
        />
        <img
          v-if="title === 'Meta Data Pending'"
          :src="linkIcon"
          alt="Create Meta Data"
          class="sync-icon-row"
          @click="handleMetaDataClick"
        />
        <img
          v-if="title === 'Soft Link Pending'"
          :src="processIcon"
          alt="Create Soft Link"
          class="sync-icon-row"
          @click="handleSoftLinkClick"
        />
      </template>
    </b-table>
  </div>
</template>

<script>
import axios from "axios";
import syncIcon from "@/assets/sync.png"; // Importing sync.png
import linkIcon from "@/assets/link.png"; // Importing link.png
import processIcon from "@/assets/process.png"; // Importing process.png
import { BPagination, BTable } from "bootstrap-vue-next";
import { BASE_URL3 } from "@/config";

export default {
  components: {
    BPagination: () =>
      import("bootstrap-vue-next").then(({ BPagination }) => BPagination),
    BTable: () => import("bootstrap-vue-next").then(({ BTable }) => BTable),
  },
  props: {
    currentPage: Number,
    perPage: Number,
    selectedOption: String,
    bidstenders: Object,
    title: String,
    currentFolder: String, // New prop to track selected folder type (total folders, archived, etc.)
  },
  data() {
    return {
      currentPage: this.currentPage,
      search_text: "",
      selectedOption: "tender",
      selectedRows: [], // Array to store selected rows
      selectAll: false, // Flag for select all checkbox
      syncIcon, // Adding the sync icon to the data property
      linkIcon, // Adding link.png to the data property
      processIcon, // Adding process.png to the data property
    };
  },
  computed: {
    fieldsWithCheckbox() {
      const existingFields =
        this.selectedOption === "tender"
          ? Object.keys(this.bidstenders.tenders[0] || {})
          : Object.keys(this.bidstenders.bids[0] || {});

      // Add Sync column at the end of the table
      let fields = [
        ...existingFields.map((field) => ({ key: field, sortable: true })),
      ];

      // Only add "Select All" and "Sync" columns if the title is not "Total Folders" or "Archived"
      if (
        this.title !== "Total Folders" &&
        this.title !== "Archived Folders" &&
        this.title !== "Errors"
      ) {
        fields.push(
          { key: "checkbox", label: "Select All", sortable: false }, // Add checkbox column
          { key: "sync", label: "Sync", sortable: false } // Add sync column
        );
      }

      return fields;
    },
    filteredItems() {
      const items =
        this.selectedOption === "tender"
          ? this.bidstenders.tenders
          : this.bidstenders.bids;

      // Filter based on the search text
      if (!this.search_text.trim()) {
        return items;
      } else {
        const searchTerm = this.search_text.trim().toLowerCase();
        return items.filter((item) =>
          Object.values(item).some((value) =>
            value.toString().toLowerCase().includes(searchTerm)
          )
        );
      }
    },
    totalRows() {
      return this.selectedOption === "tender"
        ? this.bidstenders.tenders.length
        : this.bidstenders.bids.length;
    },
    showCheckBoxSync() {
      // Show checkboxes and sync buttons only when title is "Sync Pending"
      return (
        this.title === "Sync Pending" ||
        this.title === "Meta Data Pending" ||
        this.title === "Soft Link Pending"
      );
    },
  },
  methods: {
    handleSync() {
      console.log(this.selectedOption)
      this.$emit('syncClicked',{ bidsOrTenders: this.selectedOption });
    },
    currentPageChanged(page) {
      this.$emit("update:currentPage", page);
    },
    toggleSelectAll() {
      // Toggle select all checkboxes based on the current state
      if (this.selectAll) {
        this.selectedRows = [...this.filteredItems];
      } else {
        this.selectedRows = [];
      }
    },
    updateSelectAll() {
      // Check if all items are selected
      this.selectAll = this.selectedRows.length === this.filteredItems.length;
    },

    syncRow(item) {
      // Sync specific row
      console.log("Sync row clicked:", item);
    },
    syncAllSelected() {
      // Sync all selected rows
      console.log("Sync all selected rows:", this.selectedRows);
    },
    handleMetaDataClick() {
      console.log("Meta Data Icon Clicked");
    },
    handleSoftLinkClick() {
      console.log("Soft Link Icon Clicked");
    },
  },
};
</script>

<style scoped>
@import "bootstrap/dist/css/bootstrap.css";
@import "bootstrap-vue-next/dist/bootstrap-vue-next.css";

.pgtitle {
  display: flex;
  justify-content: space-between;
}

.title {
  color: #1a4d57;
  font-weight: bold;
}

.radio-group {
  display: flex;
  justify-content: space-between;
  width: 15em;
}

.sync-icon-header,
.sync-icon-row {
  width: 20px;
  height: 20px;
  margin-left: 8px;
  cursor: pointer;
}

.select-all-label {
  margin-right: 8px; /* Adjust the value for desired spacing */
}



</style>
