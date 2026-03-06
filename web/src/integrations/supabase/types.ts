export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      bills: {
        Row: {
          apn: string
          bill_url: string | null
          city: string | null
          condition_notes: string | null
          condition_score: number | null
          condition_updated_at: string | null
          delinquent: number | null
          has_vpt: number | null
          last_payment: string | null
          location_of_property: string | null
          mailing_search_url: string | null
          owner_contact_status: string | null
          owner_contact_updated_at: string | null
          owner_details_url: string | null
          owner_email: string | null
          owner_mobile_phone: string | null
          owner_phone: string | null
          parcel_number: string | null
          pdf_file: string | null
          power_status: string | null
          prop_last_sale_date: string | null
          prop_occupancy_type: string | null
          prop_ownership_type: string | null
          property_search_url: string | null
          raw_text: string | null
          research_report_path: string | null
          research_status: string | null
          research_updated_at: string | null
          streetview_image_path: string | null
          tax_year: string | null
          tenant_verified: boolean | null
          tracer_number: string | null
          vpt_marker: string | null
        }
        Insert: {
          apn: string
          bill_url?: string | null
          city?: string | null
          condition_notes?: string | null
          condition_score?: number | null
          condition_updated_at?: string | null
          delinquent?: number | null
          has_vpt?: number | null
          last_payment?: string | null
          location_of_property?: string | null
          mailing_search_url?: string | null
          owner_contact_status?: string | null
          owner_contact_updated_at?: string | null
          owner_details_url?: string | null
          owner_email?: string | null
          owner_mobile_phone?: string | null
          owner_phone?: string | null
          parcel_number?: string | null
          pdf_file?: string | null
          power_status?: string | null
          prop_last_sale_date?: string | null
          prop_occupancy_type?: string | null
          prop_ownership_type?: string | null
          property_search_url?: string | null
          raw_text?: string | null
          research_report_path?: string | null
          research_status?: string | null
          research_updated_at?: string | null
          streetview_image_path?: string | null
          tax_year?: string | null
          tenant_verified?: boolean | null
          tracer_number?: string | null
          vpt_marker?: string | null
        }
        Update: {
          apn?: string
          bill_url?: string | null
          city?: string | null
          condition_notes?: string | null
          condition_score?: number | null
          condition_updated_at?: string | null
          delinquent?: number | null
          has_vpt?: number | null
          last_payment?: string | null
          location_of_property?: string | null
          mailing_search_url?: string | null
          owner_contact_status?: string | null
          owner_contact_updated_at?: string | null
          owner_details_url?: string | null
          owner_email?: string | null
          owner_mobile_phone?: string | null
          owner_phone?: string | null
          parcel_number?: string | null
          pdf_file?: string | null
          power_status?: string | null
          prop_last_sale_date?: string | null
          prop_occupancy_type?: string | null
          prop_ownership_type?: string | null
          property_search_url?: string | null
          raw_text?: string | null
          research_report_path?: string | null
          research_status?: string | null
          research_updated_at?: string | null
          streetview_image_path?: string | null
          tax_year?: string | null
          tenant_verified?: boolean | null
          tracer_number?: string | null
          vpt_marker?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "bills_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "parcels"
            referencedColumns: ["APN"]
          },
        ]
      }
      collection_properties: {
        Row: {
          apn: string
          collection_id: number
          created_at: string | null
          id: number
          sort_order: number | null
        }
        Insert: {
          apn: string
          collection_id: number
          created_at?: string | null
          id?: number
          sort_order?: number | null
        }
        Update: {
          apn?: string
          collection_id?: number
          created_at?: string | null
          id?: number
          sort_order?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "collection_properties_collection_id_fkey"
            columns: ["collection_id"]
            isOneToOne: false
            referencedRelation: "scouting_collections"
            referencedColumns: ["id"]
          },
        ]
      }
      favorites: {
        Row: {
          added_at: string | null
          apn: string
        }
        Insert: {
          added_at?: string | null
          apn: string
        }
        Update: {
          added_at?: string | null
          apn?: string
        }
        Relationships: [
          {
            foreignKeyName: "favorites_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "bills"
            referencedColumns: ["apn"]
          },
          {
            foreignKeyName: "favorites_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "properties_view"
            referencedColumns: ["apn"]
          },
          {
            foreignKeyName: "favorites_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "unscouted_bills"
            referencedColumns: ["apn"]
          },
        ]
      }
      housing_applications: {
        Row: {
          admin_notes: string | null
          applicant_email: string
          applicant_name: string
          applicant_phone: string | null
          background_check_consent: boolean
          children_ages: string | null
          created_at: string
          current_situation: string
          employment_status: string | null
          family_size: number
          has_children: boolean
          id: string
          maintenance_agreement: boolean
          monthly_income: string | null
          preferred_location: string | null
          special_needs: string | null
          status: string
          updated_at: string
        }
        Insert: {
          admin_notes?: string | null
          applicant_email: string
          applicant_name: string
          applicant_phone?: string | null
          background_check_consent?: boolean
          children_ages?: string | null
          created_at?: string
          current_situation: string
          employment_status?: string | null
          family_size?: number
          has_children?: boolean
          id?: string
          maintenance_agreement?: boolean
          monthly_income?: string | null
          preferred_location?: string | null
          special_needs?: string | null
          status?: string
          updated_at?: string
        }
        Update: {
          admin_notes?: string | null
          applicant_email?: string
          applicant_name?: string
          applicant_phone?: string | null
          background_check_consent?: boolean
          children_ages?: string | null
          created_at?: string
          current_situation?: string
          employment_status?: string | null
          family_size?: number
          has_children?: boolean
          id?: string
          maintenance_agreement?: boolean
          monthly_income?: string | null
          preferred_location?: string | null
          special_needs?: string | null
          status?: string
          updated_at?: string
        }
        Relationships: []
      }
      list_properties: {
        Row: {
          apn: string
          created_at: string | null
          id: number
          list_id: number
          sort_order: number | null
        }
        Insert: {
          apn: string
          created_at?: string | null
          id?: number
          list_id: number
          sort_order?: number | null
        }
        Update: {
          apn?: string
          created_at?: string | null
          id?: number
          list_id?: number
          sort_order?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "list_properties_apn_fkey"
            columns: ["apn"]
            isOneToOne: false
            referencedRelation: "bills"
            referencedColumns: ["apn"]
          },
          {
            foreignKeyName: "list_properties_apn_fkey"
            columns: ["apn"]
            isOneToOne: false
            referencedRelation: "properties_view"
            referencedColumns: ["apn"]
          },
          {
            foreignKeyName: "list_properties_apn_fkey"
            columns: ["apn"]
            isOneToOne: false
            referencedRelation: "unscouted_bills"
            referencedColumns: ["apn"]
          },
          {
            foreignKeyName: "list_properties_list_id_fkey"
            columns: ["list_id"]
            isOneToOne: false
            referencedRelation: "lists"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "list_properties_list_id_fkey"
            columns: ["list_id"]
            isOneToOne: false
            referencedRelation: "lists_with_count"
            referencedColumns: ["id"]
          },
        ]
      }
      lists: {
        Row: {
          created_at: string | null
          description: string | null
          id: number
          name: string
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          description?: string | null
          id?: number
          name: string
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          description?: string | null
          id?: number
          name?: string
          updated_at?: string | null
        }
        Relationships: []
      }
      owner_registrations: {
        Row: {
          admin_notes: string | null
          authorization_agreed: boolean
          authorization_date: string
          authorization_signature: string
          created_at: string
          document_url: string | null
          id: string
          owner_email: string
          owner_name: string
          owner_phone: string | null
          property_address: string
          property_city: string
          property_state: string
          property_zip: string | null
          status: string
          updated_at: string
        }
        Insert: {
          admin_notes?: string | null
          authorization_agreed?: boolean
          authorization_date?: string
          authorization_signature: string
          created_at?: string
          document_url?: string | null
          id?: string
          owner_email: string
          owner_name: string
          owner_phone?: string | null
          property_address: string
          property_city?: string
          property_state?: string
          property_zip?: string | null
          status?: string
          updated_at?: string
        }
        Update: {
          admin_notes?: string | null
          authorization_agreed?: boolean
          authorization_date?: string
          authorization_signature?: string
          created_at?: string
          document_url?: string | null
          id?: string
          owner_email?: string
          owner_name?: string
          owner_phone?: string | null
          property_address?: string
          property_city?: string
          property_state?: string
          property_zip?: string | null
          status?: string
          updated_at?: string
        }
        Relationships: []
      }
      parcels: {
        Row: {
          APN: string
          row_json: string | null
        }
        Insert: {
          APN: string
          row_json?: string | null
        }
        Update: {
          APN?: string
          row_json?: string | null
        }
        Relationships: []
      }
      property_reports: {
        Row: {
          address: string
          city: string
          created_at: string
          description: string | null
          id: string
          reporter_email: string | null
          reporter_name: string | null
          reporter_phone: string | null
          state: string
          status: string
          updated_at: string
          zip_code: string | null
        }
        Insert: {
          address: string
          city?: string
          created_at?: string
          description?: string | null
          id?: string
          reporter_email?: string | null
          reporter_name?: string | null
          reporter_phone?: string | null
          state?: string
          status?: string
          updated_at?: string
          zip_code?: string | null
        }
        Update: {
          address?: string
          city?: string
          created_at?: string
          description?: string | null
          id?: string
          reporter_email?: string | null
          reporter_name?: string | null
          reporter_phone?: string | null
          state?: string
          status?: string
          updated_at?: string
          zip_code?: string | null
        }
        Relationships: []
      }
      results: {
        Row: {
          apn: string
          pdf_file: string | null
        }
        Insert: {
          apn: string
          pdf_file?: string | null
        }
        Update: {
          apn?: string
          pdf_file?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "results_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "parcels"
            referencedColumns: ["APN"]
          },
        ]
      }
      scout_results: {
        Row: {
          apn: string
          collection_id: number | null
          flyered: number
          follow_up: number
          id: number
          latitude: number | null
          longitude: number | null
          notes: string | null
          scouted_at: string | null
        }
        Insert: {
          apn: string
          collection_id?: number | null
          flyered?: number
          follow_up?: number
          id?: number
          latitude?: number | null
          longitude?: number | null
          notes?: string | null
          scouted_at?: string | null
        }
        Update: {
          apn?: string
          collection_id?: number | null
          flyered?: number
          follow_up?: number
          id?: number
          latitude?: number | null
          longitude?: number | null
          notes?: string | null
          scouted_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "scout_results_collection_id_fkey"
            columns: ["collection_id"]
            isOneToOne: false
            referencedRelation: "scouting_collections"
            referencedColumns: ["id"]
          },
        ]
      }
      scouting_collections: {
        Row: {
          created_at: string | null
          description: string | null
          id: number
          name: string
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          description?: string | null
          id?: number
          name: string
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          description?: string | null
          id?: number
          name?: string
          updated_at?: string | null
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
      volunteers: {
        Row: {
          availability: string[] | null
          created_at: string
          email: string
          id: string
          name: string
          notes: string | null
          phone: string | null
          skills: string[] | null
          status: string
          updated_at: string
        }
        Insert: {
          availability?: string[] | null
          created_at?: string
          email: string
          id?: string
          name: string
          notes?: string | null
          phone?: string | null
          skills?: string[] | null
          status?: string
          updated_at?: string
        }
        Update: {
          availability?: string[] | null
          created_at?: string
          email?: string
          id?: string
          name?: string
          notes?: string | null
          phone?: string | null
          skills?: string[] | null
          status?: string
          updated_at?: string
        }
        Relationships: []
      }
    }
    Views: {
      lists_with_count: {
        Row: {
          cnt: number | null
          description: string | null
          id: number | null
          name: string | null
        }
        Insert: {
          cnt?: never
          description?: string | null
          id?: number | null
          name?: string | null
        }
        Update: {
          cnt?: never
          description?: string | null
          id?: number | null
          name?: string | null
        }
        Relationships: []
      }
      properties_view: {
        Row: {
          apn: string | null
          city: string | null
          is_scouted: boolean | null
          location_of_property: string | null
        }
        Insert: {
          apn?: string | null
          city?: string | null
          is_scouted?: never
          location_of_property?: string | null
        }
        Update: {
          apn?: string | null
          city?: string | null
          is_scouted?: never
          location_of_property?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "bills_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "parcels"
            referencedColumns: ["APN"]
          },
        ]
      }
      unscouted_bills: {
        Row: {
          apn: string | null
          city: string | null
          location_of_property: string | null
        }
        Insert: {
          apn?: string | null
          city?: string | null
          location_of_property?: string | null
        }
        Update: {
          apn?: string | null
          city?: string | null
          location_of_property?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "bills_apn_fkey"
            columns: ["apn"]
            isOneToOne: true
            referencedRelation: "parcels"
            referencedColumns: ["APN"]
          },
        ]
      }
    }
    Functions: {
      get_bills_filtered:
        | {
            Args: {
              p_city?: string
              p_condition?: string
              p_delinquent?: number
              p_fav?: number
              p_limit?: number
              p_offset?: number
              p_order?: string
              p_outofstate?: number
              p_power?: string
              p_q?: string
              p_sort?: string
              p_vpt?: number
              p_zip?: string
            }
            Returns: Json
          }
        | {
            Args: {
              p_city: string
              p_condition: string
              p_delinquent: number
              p_fav: number
              p_limit: number
              p_offset: number
              p_order: string
              p_outofstate: number
              p_power: string
              p_q: string
              p_research: string
              p_sort: string
              p_vpt: number
              p_zip: string
            }
            Returns: Json
          }
      get_bills_for_map: {
        Args: {
          p_city?: string
          p_delinquent?: number
          p_fav?: number
          p_power?: string
          p_q?: string
          p_vpt?: number
          p_zip?: string
        }
        Returns: Json
      }
      get_unscouted_bills: {
        Args: { p_list_id?: number }
        Returns: {
          apn: string
          city: string
          location_of_property: string
        }[]
      }
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      is_admin: { Args: never; Returns: boolean }
    }
    Enums: {
      app_role: "admin" | "moderator" | "user"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "moderator", "user"],
    },
  },
} as const
