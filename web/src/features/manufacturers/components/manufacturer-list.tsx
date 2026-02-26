"use client";

import Link from "next/link";
import { MessageSquare } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Manufacturer } from "@/types/api";

interface ManufacturerListProps {
  manufacturers: Manufacturer[];
  onRowClick?: (manufacturer: Manufacturer) => void;
}

export function ManufacturerList({ manufacturers, onRowClick }: ManufacturerListProps) {
  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>メーカー名</TableHead>
            <TableHead>連絡先</TableHead>
            <TableHead>対応商品</TableHead>
            <TableHead>1日上限</TableHead>
            <TableHead>共有方式</TableHead>
            <TableHead>ステータス</TableHead>
            <TableHead>チャット</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {manufacturers.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                該当するメーカーがありません
              </TableCell>
            </TableRow>
          ) : (
            manufacturers.map((manufacturer) => (
              <TableRow
                key={manufacturer.id}
                className="cursor-pointer hover:bg-accent/50"
                onClick={() => onRowClick?.(manufacturer)}
              >
                <TableCell className="font-medium">{manufacturer.name}</TableCell>
                <TableCell>
                  <div>{manufacturer.email}</div>
                  {manufacturer.phone && (
                    <div className="text-xs text-muted-foreground">
                      {manufacturer.phone}
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {manufacturer.supported_products.slice(0, 3).map((product) => (
                      <Badge key={product} variant="secondary" className="text-xs">
                        {product}
                      </Badge>
                    ))}
                    {manufacturer.supported_products.length > 3 && (
                      <Badge variant="outline" className="text-xs">
                        +{manufacturer.supported_products.length - 3}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {manufacturer.daily_order_limit}件
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {manufacturer.sharing_method === "drive" ? "DRIVE" : "ポータル"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={manufacturer.is_active ? "default" : "secondary"}>
                    {manufacturer.is_active ? "有効" : "無効"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Link
                    href={`/chat?manufacturer=${manufacturer.id}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button variant="ghost" size="icon">
                      <MessageSquare className="h-4 w-4" />
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
